#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归档索引模块（T2 + T3 + T4 核心）
- SQLite FTS5 全文索引
- SHA256 查重
- 条款切分与定位
- 文件元数据管理

所有操作通过 ArchiveDB 类对外提供，启动时初始化，运行时增量更新。
"""
import os
import sys
import re
import hashlib
import sqlite3
import time
import threading
from datetime import datetime

# ---------- 常量 ----------
DB_NAME = 'archive.db'
# 支持"第一条"和"第第一条"两种格式，以及"第X章""第X编"等变体
CLAUSE_PAT = re.compile(r'^(第(?:第)?([一二三四五六七八九十百千零\d]+)[章节条编分讲天]|专题[一二三四五六七八九十百千零]+|[一二三四五六七八九十]+[、.．])\s*(.*)')
MAX_SHA_LENGTH = 16  # 短哈希用于文件名消歧

# ---------- 条款切分 ----------
def split_clauses(text):
    """按"第X条"结构切分文本为条款列表。
    返回 [(条款号, 条款全文), ...]，无法识别条款结构的文档返回 [(全文, None)]。"""
    lines = text.split('\n')
    clauses = []
    current_number = None
    current_lines = []
    
    for line in lines:
        m = CLAUSE_PAT.match(line.strip())
        if m:
            # 保存前一个条款
            if current_number is not None and current_lines:
                clauses.append((current_number, '\n'.join(current_lines).strip()))
            current_number = m.group(0).split()[0]
            # Content is always group(3) - everything after \s*
            current_lines = [m.group(3) if m.group(3) else line.strip()]
        else:
            if current_number is not None:
                current_lines.append(line)
            else:
                # 没有条款结构，归入全文
                pass
    
    # 保存最后一个条款
    if current_number is not None and current_lines:
        clauses.append((current_number, '\n'.join(current_lines).strip()))
    
    return clauses

def extract_clauses(text):
    """提取条款：如果文档有条款结构则返回条款列表，否则返回 [(全文, None)]。"""
    clauses = split_clauses(text)
    if clauses:
        return clauses
    # 没有识别到条款结构：以 None 为 clause_num，text 为 clause_text，确保索引
    return [(None, text)]

# ---------- bigram 兜底匹配 ----------
def _extract_bigram_chars(text):
    """提取文本中的中文字符集（用于 bigram 匹配）。"""
    chars = re.findall(r'[\u4e00-\u9fff]', text)
    return set(chars), set(''.join(chars[i:i+2]) for i in range(len(chars) - 1))

# ---------- 文件哈希 ----------
def file_sha256(path):
    """计算文件 SHA256 哈希值，返回 hex 字符串。"""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
    except Exception:
        return ''
    return h.hexdigest()

def text_sha256(text):
    """计算文本 SHA256 哈希值（用于查重）。"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# ---------- SQLite 索引 ----------
class ArchiveDB:
    """归档元数据与 FTS5 索引管理器。"""
    
    def __init__(self, db_path):
        """初始化数据库连接。
        db_path: archive.db 完整路径。
        启动时自动创建表结构（FTS5 不可用则降级为普通索引表）。"""
        self.db_path = db_path
        self.conn = None
        self.lock = threading.Lock()
        self._init_db()
    
    def _get_conn(self):
        """获取数据库连接，懒初始化。
        注意：必须设置 check_same_thread=False，因为连接可能在 HTTP 线程池中访问。"""
        if self.conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute('PRAGMA journal_mode=WAL')
            self.conn.execute('PRAGMA synchronous=NORMAL')
        return self.conn
    
    def _init_db(self):
        """创建三表：file_meta + hash_index + fts_index（或降级表）。"""
        conn = self._get_conn()
        
        # 文件元数据表
        conn.execute('''
            CREATE TABLE IF NOT EXISTS file_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name TEXT NOT NULL,      -- 原始文件名
                archive_name TEXT NOT NULL,       -- 归档文件名（.txt）
                archive_path TEXT NOT NULL,       -- 归档文件完整路径
                original_path TEXT,               -- 原件副本路径
                sha256 TEXT NOT NULL,             -- 全文 SHA256
                file_size INTEGER DEFAULT 0,      -- 文件大小
                upload_time TEXT NOT NULL,        -- 上传时间
                page_count INTEGER DEFAULT 0,     -- 页数
                extract_method TEXT,              -- 提取方式（PDF提取/docx提取等）
                clause_count INTEGER DEFAULT 0,   -- 条款数
                UNIQUE(sha256)
            )
        ''')
        
        # 哈希查重表
        conn.execute('''
            CREATE TABLE IF NOT EXISTS hash_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sha256 TEXT NOT NULL UNIQUE,
                file_count INTEGER DEFAULT 1
            )
        ''')
        
        # 降级为普通 LIKE 全文索引表（对中文支持更好）
        self.use_fts5 = False
        conn.execute('''
            CREATE TABLE IF NOT EXISTS fts_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                clause_text TEXT NOT NULL,
                clause_number TEXT,
                FOREIGN KEY(doc_id) REFERENCES file_meta(id)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_fts_text ON fts_index(clause_text)')
        print('[索引] 使用 LIKE 全文索引')
        
        conn.commit()
    
    def is_duplicate(self, sha256):
        """检查 SHA256 是否已存在。"""
        conn = self._get_conn()
        cursor = conn.execute('SELECT id, original_name FROM file_meta WHERE sha256 = ?', (sha256,))
        row = cursor.fetchone()
        if row:
            return {'duplicate': True, 'existing_name': row[1]}
        return {'duplicate': False}
    
    def add_file(self, original_name, archive_name, archive_path, original_path, 
                 sha256, file_size, extract_method, page_count):
        """新增文件索引。返回 (success, message)。"""
        with self.lock:
            conn = self._get_conn()
            
            # 查重
            dup = self.is_duplicate(sha256)
            if dup['duplicate']:
                return False, f'重复文件（SHA256 已存在：{dup["existing_name"]}）'
            
            # 检查文件名是否重复
            cursor = conn.execute('SELECT id FROM file_meta WHERE original_name = ?', (original_name,))
            if cursor.fetchone():
                return False, f'文件名重复：{original_name}'
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 切分条款
            clauses = extract_clauses(open(archive_path, encoding='utf-8').read())
            clause_count = len(clauses)
            
            # 插入元数据
            conn.execute('''
                INSERT INTO file_meta (original_name, archive_name, archive_path, original_path,
                                       sha256, file_size, upload_time, page_count, extract_method, clause_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (original_name, archive_name, archive_path, original_path,
                  sha256, file_size, now, page_count, extract_method, clause_count))
            
            doc_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            # 插入 FTS5 索引
            for clause_num, clause_text in clauses:
                if clause_text:
                    if self.use_fts5:
                        conn.execute(
                            'INSERT INTO fts_index(clause_text, clause_number, doc_id) VALUES (?, ?, ?)',
                            (clause_text, clause_num, doc_id)
                        )
                    else:
                        conn.execute(
                            'INSERT INTO fts_index(doc_id, clause_text, clause_number) VALUES (?, ?, ?)',
                            (doc_id, clause_text, clause_num)
                        )
            
            # 更新 hash_index
            conn.execute('INSERT OR IGNORE INTO hash_index(sha256) VALUES (?)', (sha256,))
            
            conn.commit()
            return True, f'归档成功：{archive_name}（条款{clause_count}条）'
    
    def search(self, query, page=1, page_size=20):
        """搜索索引。返回 (results, total, page, page_size)。"""
        conn = self._get_conn()
        terms = query.split()
        
        if not terms:
            return [], 0, page, page_size
        
        if self.use_fts5:
            # FTS5 查询
            query_parts = ' '.join(f'"{t}*" OR {t}' for t in terms)
            
            # 主查询：FTS5 匹配（按命中数排序，不依赖 bm258）
            base_query = f'''
                SELECT DISTINCT fm.id, fm.original_name, fm.archive_name, fm.clause_count,
                       fi.clause_text, fi.clause_number
                FROM fts_index fi
                JOIN file_meta fm ON fm.id = fi.doc_id
                WHERE fts_index MATCH ?
                LIMIT ? OFFSET ?
            '''
            # FTS5 MATCH 语法
            match_query = ' AND '.join(f'"{t}*"' for t in terms)
            
            cursor = conn.execute(base_query, (match_query, page_size, (page - 1) * page_size))
        else:
            # 降级查询：LIKE 匹配
            # 多 term 组合查询：先 OR 获取所有候选，然后在 Python 侧过滤 AND
            where_clause = ' OR '.join([f'fi.clause_text LIKE ?' for _ in terms])
            params_base = [f'%{t}%' for t in terms]
            base_query = f'''
                SELECT fm.id, fm.original_name, fm.archive_name, fm.clause_count,
                       fi.clause_text, fi.clause_number
                FROM fts_index fi
                JOIN file_meta fm ON fm.id = fi.doc_id
                WHERE {where_clause}
                ORDER BY fm.id
            '''
            params = params_base  # 不加 LIMIT，全部取回后在 Python 侧分页
            cursor = conn.execute(base_query, params)
        
        all_rows = cursor.fetchall()
        
        # LIKE 分支：Python 侧 AND 过滤 + 分页 + 计数
        if not self.use_fts5:
            # 按 doc_id 聚合全文
            doc_full_text = {}  # doc_id -> 完整 clauses 拼接
            for row_id, name, archive_name, clause_count, clause_text, clause_number in all_rows:
                if row_id not in doc_full_text:
                    doc_full_text[row_id] = ''
                doc_full_text[row_id] += ' ' + (clause_text or '')
            
            # AND 过滤：每个 term 必须出现在某行的 clause_text 中
            filtered_docs = set()
            for doc_id, full_text in doc_full_text.items():
                if all(t in full_text for t in terms):
                    filtered_docs.add(doc_id)
            
            # 从 all_rows 中筛选 AND 命中的行
            filtered_rows = [r for r in all_rows if r[0] in filtered_docs]
            
            # 计数（所有命中 AND 的文件数）
            total = len(filtered_docs)
            
            # 分页
            filtered_rows = filtered_rows[(page - 1) * page_size : page * page_size]
        else:
            filtered_rows = all_rows
            # FTS5 计数
            count_query = f'''
                SELECT COUNT(DISTINCT fm.id)
                FROM fts_index fi
                JOIN file_meta fm ON fm.id = fi.doc_id
                WHERE fts_index MATCH ?
            '''
            total = conn.execute(count_query, (match_query,)).fetchone()[0]
        
        # Bigram 兜底：仅对单 term 查询且未命中且包含中文时，回退到 bigram 匹配
        # 多 term 查询（如"劳动 分页"）AND 过滤失败时应返回 0，不触发 bigram
        if total == 0 and not self.use_fts5 and len(terms) == 1 and any('\u4e00' <= c <= '\u9fff' for c in query):
            bigram_results, total = self._search_bigram(query, page, page_size)
            # bigram 结果已是最终格式，直接返回
            return bigram_results, total, page, page_size
        
        rows = filtered_rows
        
        # 结果聚合：按文件分组
        results = {}
        for row_id, name, archive_name, clause_count, clause_text, clause_number in rows:
            if row_id not in results:
                results[row_id] = {
                    'name': name,
                    'archive_name': archive_name,
                    'clause_count': clause_count,
                    'hits': []
                }
            
            hit = {'line_text': clause_text[:200]}  # 截断长文本
            if clause_number:
                hit['clause'] = clause_number
            results[row_id]['hits'].append(hit)
        
        # 按命中数降序
        sorted_results = sorted(results.values(), key=lambda x: len(x['hits']), reverse=True)
        
        return sorted_results[:page_size], total, page, page_size
    
    def _search_bigram(self, query, page=1, page_size=20):
        """Bigram 兜底搜索：LIKE 未命中时对全文进行 bigram 匹配。
        适用于跨字查询（如'劳动者解除'）——LIKE 需完整子串，bigram 可匹配跨字组合。
        返回 (results, total)。"""
        conn = self._get_conn()
        
        # 提取查询词的中文字符集
        query_chars = re.findall(r'[\u4e00-\u9fff]', query)
        if len(query_chars) < 2:
            return [], 0
        
        query_bigrams = set(''.join(query_chars[i:i+2]) for i in range(len(query_chars) - 1))
        if not query_bigrams:
            return [], 0
        
        # 获取所有 clause_text + clause_number 及 doc_id
        rows = conn.execute(
            'SELECT id, doc_id, clause_text, clause_number FROM fts_index'
        ).fetchall()
        
        # 按 doc_id 分组，在 Python 侧做 bigram 匹配
        file_hits = {}  # doc_id -> {'matched_bigrams': set, 'hits': list}
        
        for row_id, doc_id, clause_text, clause_number in rows:
            clause_chars = re.findall(r'[\u4e00-\u9fff]', clause_text)
            if len(clause_chars) < 2:
                continue
            clause_bigrams = set(''.join(clause_chars[i:i+2]) for i in range(len(clause_chars) - 1))
            
            matched = query_bigrams & clause_bigrams
            if matched:
                if doc_id not in file_hits:
                    file_hits[doc_id] = {'matched_bigrams': set(), 'hits': []}
                file_hits[doc_id]['matched_bigrams'].update(matched)
                file_hits[doc_id]['hits'].append({
                    'line_text': clause_text[:200],
                    'clause': clause_number if clause_number else ''
                })
        
        if not file_hits:
            return [], 0
        
        # 按命中 bigram 数量排序
        total = len(file_hits)
        sorted_docs = sorted(file_hits.items(), key=lambda x: len(x[1]['matched_bigrams']), reverse=True)
        
        # 分页
        sorted_docs = sorted_docs[(page-1)*page_size: page*page_size]
        
        # 构建结果
        results = []
        for doc_id, data in sorted_docs:
            # 查 file_meta 获取 name
            meta = conn.execute(
                'SELECT original_name, archive_name, clause_count FROM file_meta WHERE id = ?',
                (doc_id,)
            ).fetchone()
            
            if meta:
                results.append({
                    'name': meta[0],
                    'archive_name': meta[1],
                    'clause_count': meta[2],
                    'hits': data['hits']
                })
        
        return results, total
    
    def delete_file(self, archive_name):
        """删除文件索引。返回 (success, message)。"""
        with self.lock:
            conn = self._get_conn()
            
            # 查找文件
            cursor = conn.execute('SELECT id, archive_path, original_path FROM file_meta WHERE archive_name = ?', (archive_name,))
            row = cursor.fetchone()
            if not row:
                return False, '文件不存在'
            
            doc_id, archive_path, original_path = row
            
            # 删除 FTS5 索引
            if self.use_fts5:
                conn.execute('DELETE FROM fts_index WHERE doc_id = ?', (doc_id,))
            else:
                conn.execute('DELETE FROM fts_index WHERE doc_id = ?', (doc_id,))
            
            # 删除元数据
            conn.execute('DELETE FROM file_meta WHERE id = ?', (doc_id,))
            
            # 清理文件
            if archive_path and os.path.exists(archive_path):
                os.remove(archive_path)
            if original_path and os.path.exists(original_path):
                os.remove(original_path)
            
            conn.commit()
            return True, f'已删除：{archive_name}'
    
    def list_files(self, page=1, page_size=20):
        """列出所有归档文件。"""
        conn = self._get_conn()
        total = conn.execute('SELECT COUNT(*) FROM file_meta').fetchone()[0]
        cursor = conn.execute('''
            SELECT id, original_name, archive_name, upload_time, file_size, page_count, clause_count
            FROM file_meta
            ORDER BY upload_time DESC
            LIMIT ? OFFSET ?
        ''', (page_size, (page - 1) * page_size))
        
        rows = cursor.fetchall()
        files = []
        for row in rows:
            files.append({
                'id': row[0],
                'name': row[1],
                'archive_name': row[2],
                'upload_time': row[3],
                'file_size': row[4],
                'page_count': row[5],
                'clause_count': row[6]
            })
        
        return files, total
    
    def close(self):
        """关闭数据库连接。"""
        if self.conn:
            self.conn.close()
            self.conn = None


def init_archive_db(archive_root):
    """初始化归档数据库。
    archive_root: 归档根目录（如 ~/检索归档）。
    返回 ArchiveDB 实例。"""
    db_path = os.path.join(archive_root, DB_NAME)
    return ArchiveDB(db_path)
