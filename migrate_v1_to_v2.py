#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_v1_to_v2.py — 旧归档（v1）迁移到 v2 归档结构

v1 结构：单一 归档/ 目录下只有 txt 文件，无原件、无元数据、无查重
v2 结构：
  files/       — 原始文件副本（PDF/DOCX/XLSX/TXT 等）
  texts/       — 转换后的纯文本（与 v1 归档/ 内容一致）
  archive.db   — SQLite 元数据索引（文件信息、SHA256、处理记录）

用法：
  python3 migrate_v1_to_v2.py [旧归档目录路径]

如果不传参数，默认查找程序目录下的"归档/"目录。
迁移后会在目标目录下生成 files/、texts/、archive.db，旧 txt 文件保留不动。
"""
import os
import sys
import hashlib
import sqlite3
import shutil
import time
from datetime import datetime

def sha256_file(path):
    """计算文件的 SHA256 哈希值"""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def create_v2_schema(db_path):
    """创建 v2 归档数据库 schema"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS file_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,       -- 原始文件名
            text_name TEXT NOT NULL,           -- 对应的 txt 文件名
            file_hash TEXT,                    -- 原文件 SHA256
            text_hash TEXT,                    -- 文本内容 SHA256
            file_type TEXT,                    -- 文件类型：pdf/docx/xlsx/txt
            archive_dir TEXT,                  -- 归档所在的目录
            text_size INTEGER,                 -- 文本文件大小（字节）
            processed_at TEXT,                 -- 处理时间
            created_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'ok'           -- ok / error / duplicate
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS hash_index (
            file_hash TEXT PRIMARY KEY,         -- 原文件哈希索引，用于查重
            text_name TEXT,
            original_name TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS migration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_dir TEXT,
            migrated_at TEXT DEFAULT (datetime('now')),
            total_files INTEGER DEFAULT 0,
            migrated_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

def detect_file_type(filename):
    """根据扩展名检测文件类型"""
    ext = os.path.splitext(filename)[1].lower()
    type_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.doc': 'doc',
        '.xlsx': 'xlsx',
        '.xls': 'xls',
        '.txt': 'txt',
    }
    return type_map.get(ext, 'unknown')

def migrate_v1_to_v2(source_dir):
    """
    将 v1 归档目录迁移到 v2 结构
    
    流程：
    1. 扫描所有 .txt 文件
    2. 尝试在 source_dir 下找对应的原始文件（同名不同扩展名）
    3. 复制原始文件到 files/，文本到 texts/
    4. 计算 SHA256，记录到 archive.db
    5. 查重：如果 file_hash 已存在，标记为 duplicate
    """
    if not os.path.isdir(source_dir):
        print(f'错误：目录不存在: {source_dir}')
        return False

    # 创建 v2 目录结构
    files_dir = os.path.join(source_dir, 'files')
    texts_dir = os.path.join(source_dir, 'texts')
    db_path = os.path.join(source_dir, 'archive.db')

    os.makedirs(files_dir, exist_ok=True)
    os.makedirs(texts_dir, exist_ok=True)

    # 创建数据库
    conn = create_v2_schema(db_path)
    cur = conn.cursor()

    # 记录迁移日志
    cur.execute('INSERT INTO migration_log (source_dir) VALUES (?)', (source_dir,))
    migration_id = cur.lastrowid

    # 扫描所有 txt 文件
    txt_files = sorted([f for f in os.listdir(source_dir) if f.endswith('.txt') and f != 'archive.db'])
    total = len(txt_files)
    print(f'发现 {total} 个 txt 归档文件')

    migrated = 0
    skipped = 0
    errors = 0

    for txt_name in txt_files:
        txt_path = os.path.join(source_dir, txt_name)
        try:
            # 去掉 .txt 后缀，尝试找原始文件
            base_name = os.path.splitext(txt_name)[0]
            original_file = None
            for ext in ('.pdf', '.docx', '.doc', '.xlsx', '.xls'):
                candidate = os.path.join(source_dir, base_name + ext)
                if os.path.isfile(candidate):
                    original_file = candidate
                    break

            # 计算文本哈希
            text_hash = sha256_file(txt_path)
            text_size = os.path.getsize(txt_path)

            if original_file:
                # 有原文文件：复制到 files/
                file_hash = sha256_file(original_file)
                file_type = detect_file_type(original_file)
                orig_basename = os.path.basename(original_file)

                # 查重（按原文哈希）
                cur.execute('SELECT text_name FROM hash_index WHERE file_hash = ?', (file_hash,))
                row = cur.fetchone()
                if row:
                    # 重复文件
                    cur.execute('''
                        INSERT INTO file_meta (original_name, text_name, file_hash, text_hash,
                                              file_type, archive_dir, text_size, processed_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 'duplicate')
                    ''', (orig_basename, txt_name, file_hash, text_hash, file_type,
                          source_dir, text_size))
                    skipped += 1
                    print(f'  [重复] {orig_basename} -> {txt_name}')
                else:
                    # 新文件：存入 hash_index
                    cur.execute('''
                        INSERT INTO file_meta (original_name, text_name, file_hash, text_hash,
                                              file_type, archive_dir, text_size, processed_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 'ok')
                    ''', (orig_basename, txt_name, file_hash, text_hash, file_type,
                          source_dir, text_size))
                    cur.execute('''
                        INSERT INTO hash_index (file_hash, text_name, original_name)
                        VALUES (?, ?, ?)
                    ''', (file_hash, txt_name, orig_basename))

                    # 复制原件到 files/
                    dest_file = os.path.join(files_dir, orig_basename)
                    shutil.copy2(original_file, dest_file)

                    # 复制文本到 texts/
                    dest_text = os.path.join(texts_dir, txt_name)
                    shutil.copy2(txt_path, dest_text)

                    migrated += 1
                    print(f'  [迁移] {orig_basename} ({file_type}) -> {txt_name}')
            else:
                # 无原文文件：按文本哈希查重（与所有已有记录的 text_hash 对比）
                cur.execute('SELECT text_name FROM file_meta WHERE text_hash = ?', (text_hash,))
                row = cur.fetchone()
                if row:
                    # 重复文本
                    cur.execute('''
                        INSERT INTO file_meta (original_name, text_name, file_hash, text_hash,
                                              file_type, archive_dir, text_size, processed_at, status)
                        VALUES (?, ?, '', ?, 'text', ?, ?, datetime('now'), 'duplicate')
                    ''', ('(无原文/重复)', txt_name, text_hash, source_dir, text_size))
                    skipped += 1
                    print(f'  [重复文本] {txt_name}')
                else:
                    cur.execute('''
                        INSERT INTO file_meta (original_name, text_name, file_hash, text_hash,
                                              file_type, archive_dir, text_size, processed_at, status)
                        VALUES (?, ?, '', ?, 'text', ?, ?, datetime('now'), 'ok')
                    ''', ('(无原文)', txt_name, text_hash, source_dir, text_size))

                    # 复制文本到 texts/
                    dest_text = os.path.join(texts_dir, txt_name)
                    shutil.copy2(txt_path, dest_text)

                    migrated += 1
                    print(f'  [纯文本] {txt_name}')

            conn.commit()

        except Exception as e:
            errors += 1
            print(f'  [错误] {txt_name}: {e}')

    # 更新迁移日志
    cur.execute('''
        UPDATE migration_log SET total_files=?, migrated_count=?, skipped_count=?, error_count=?
        WHERE id=?
    ''', (total, migrated, skipped, errors, migration_id))
    conn.commit()
    conn.close()

    print(f'\n迁移完成：')
    print(f'  总计: {total}')
    print(f'  迁移: {migrated}')
    print(f'  跳过（重复）: {skipped}')
    print(f'  错误: {errors}')
    print(f'  数据库: {db_path}')
    print(f'  原文文件: {files_dir}')
    print(f'  文本文件: {texts_dir}')

    return True

def check_duplicate_in_v2(source_dir, new_file_path):
    """
    在 v2 归档中检查新文件是否重复
    
    用法：在上传文件前先调用此函数检查
    返回 (is_duplicate, existing_meta)
    """
    db_path = os.path.join(source_dir, 'archive.db')
    if not os.path.exists(db_path):
        return False, None

    file_hash = sha256_file(new_file_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT original_name, text_name, processed_at FROM file_meta WHERE file_hash = ? AND status = ?',
                (file_hash, 'ok'))
    row = cur.fetchone()
    conn.close()

    if row:
        return True, {'original_name': row[0], 'text_name': row[1], 'processed_at': row[2]}
    return False, None

if __name__ == '__main__':
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        # 默认查找程序目录下的"归档/"
        base = os.path.dirname(os.path.realpath(__file__))
        source = os.path.join(base, '归档')

    print(f'迁移 v1 -> v2: {source}')
    print(f'=' * 60)
    migrate_v1_to_v2(source)
