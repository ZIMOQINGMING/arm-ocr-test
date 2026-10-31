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
    # 没有识别到条款结构
    return [(text, None)]

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
            where_clauses = ' OR '.join([f'fi.clause_text LIKE ?' for _ in terms])
            base_query = f'''
                SELECT DISTINCT fm.id, fm.original_name, fm.archive_name, fm.clause_count,
                       fi.clause_text, fi.clause_number
                FROM fts_index fi
                JOIN file_meta fm ON fm.id = fi.doc_id
                WHERE {where_clauses}
                LIMIT ? OFFSET ?
            '''
            params = [f'%{t}%' for t in terms] + [page_size, (page - 1) * page_size]
            
            cursor = conn.execute(base_query, params)
        
        rows = cursor.fetchall()
        
        # 统计总数
        if self.use_fts5:
            count_query = f'''
                SELECT COUNT(DISTINCT fm.id)
                FROM fts_index fi
                JOIN file_meta fm ON fm.id = fi.doc_id
                WHERE fts_index MATCH ?
            '''
            total = conn.execute(count_query, (match_query,)).fetchone()[0]
        else:
            count_where = ' OR '.join([f'fi.clause_text LIKE ?' for _ in terms])
            total = conn.execute(
                f'SELECT COUNT(DISTINCT fm.id) FROM fts_index fi JOIN file_meta fm ON fm.id = fi.doc_id WHERE {count_where}',
                [f'%{t}%' for t in terms]
            ).fetchone()[0]
        
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
