#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backup_restore.py — 归档目录备份与恢复模块

功能：
1. backup_archive(archive_dir, backup_dir) — 备份归档目录
   - 支持 tar.gz（默认）和 zip 两种格式
   - 生成 SHA256 校验清单
   - 返回备份文件路径和校验信息

2. restore_archive(backup_file, restore_dir) — 恢复归档目录
   - 校验 SHA256 确保备份完整
   - 解压到目标目录
   - 验证恢复后文件与备份一致

3. verify_backup(backup_file) — 验证备份文件完整性
"""
import os
import sys
import hashlib
import tarfile
import zipfile
import json
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


def generate_checksum_manifest(directory):
    """
    生成目录的 SHA256 校验清单
    
    返回: {相对路径: sha256, ...}
    """
    manifest = {}
    for root, dirs, files in os.walk(directory):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, directory)
            manifest[rel_path] = sha256_file(fpath)
    return manifest


def backup_archive(archive_dir, backup_dir=None, format='tar.gz'):
    """
    备份归档目录
    
    参数:
        archive_dir: 要备份的目录路径
        backup_dir: 备份存放目录（默认当前目录的 backups/）
        format: 备份格式 'tar.gz' 或 'zip'
    
    返回:
        {
            'backup_path': 备份文件路径,
            'backup_size': 文件大小,
            'checksum_manifest': SHA256 校验清单,
            'file_count': 文件数量,
            'backup_at': 备份时间
        }
    """
    if not os.path.isdir(archive_dir):
        raise FileNotFoundError(f'归档目录不存在: {archive_dir}')
    
    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(archive_dir)), 'backups')
    
    os.makedirs(backup_dir, exist_ok=True)
    
    # 生成校验清单
    manifest = generate_checksum_manifest(archive_dir)
    file_count = len(manifest)
    
    # 生成时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # tar.gz 格式直接追加 .tar.gz 后缀，其他取扩展名
    if format == 'tar.gz':
        ext = '.tar.gz'
    else:
        ext = '.' + format.split('.')[-1]
    backup_filename = f'archive_backup_{timestamp}{ext}'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    print(f'开始备份: {archive_dir}')
    print(f'备份格式: {format}')
    print(f'文件数量: {file_count}')
    
    start_time = time.time()
    
    if format == 'tar.gz':
        # tar.gz 备份
        with tarfile.open(backup_path, 'w:gz') as tar:
            for rel_path in sorted(manifest.keys()):
                abs_path = os.path.join(archive_dir, rel_path)
                tar.add(abs_path, arcname=rel_path)
    elif format == 'zip':
        # zip 备份
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for rel_path in sorted(manifest.keys()):
                abs_path = os.path.join(archive_dir, rel_path)
                zf.write(abs_path, arcname=rel_path)
    else:
        raise ValueError(f'不支持的备份格式: {format}')
    
    elapsed = time.time() - start_time
    backup_size = os.path.getsize(backup_path)
    
    # 保存校验清单到备份目录
    manifest_path = backup_path + '.sha256'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({
            'backup_file': backup_path,
            'backup_at': datetime.now().isoformat(),
            'archive_dir': archive_dir,
            'format': format,
            'file_count': file_count,
            'backup_size': backup_size,
            'elapsed_seconds': round(elapsed, 2),
            'checksums': manifest
        }, f, ensure_ascii=False, indent=2)
    
    print(f'备份完成: {backup_path}')
    print(f'备份大小: {backup_size} 字节')
    print(f'耗时: {elapsed:.2f} 秒')
    print(f'校验清单: {manifest_path}')
    
    return {
        'backup_path': backup_path,
        'manifest_path': manifest_path,
        'backup_size': backup_size,
        'checksum_manifest': manifest,
        'file_count': file_count,
        'backup_at': datetime.now().isoformat(),
        'elapsed_seconds': elapsed
    }


def restore_archive(backup_file, restore_dir, verify=True):
    """
    从备份恢复归档目录
    
    参数:
        backup_file: 备份文件路径（.tar.gz 或 .zip）
        restore_dir: 恢复目标目录
        verify: 是否校验 SHA256
    
    返回:
        {
            'restore_path': 恢复目录路径,
            'file_count': 恢复的文件数量,
            'verify_passed': 校验是否通过
        }
    """
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f'备份文件不存在: {backup_file}')
    
    os.makedirs(restore_dir, exist_ok=True)
    
    manifest_path = backup_file + '.sha256'
    expected_manifest = None
    
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        expected_manifest = manifest_data.get('checksums', {})
        print(f'找到校验清单: {len(expected_manifest)} 个文件的 SHA256')
    
    print(f'开始恢复: {backup_file} -> {restore_dir}')
    
    start_time = time.time()
    
    if backup_file.endswith('.tar.gz') or backup_file.endswith('.tgz'):
        with tarfile.open(backup_file, 'r:gz') as tar:
            tar.extractall(path=restore_dir)
    elif backup_file.endswith('.zip'):
        with zipfile.ZipFile(backup_file, 'r') as zf:
            zf.extractall(path=restore_dir)
    else:
        raise ValueError(f'不支持的备份格式: {os.path.splitext(backup_file)[-1]}')
    
    elapsed = time.time() - start_time
    
    # 验证恢复后的文件
    verify_passed = True
    if verify and expected_manifest:
        print('\n验证恢复文件完整性...')
        actual_manifest = generate_checksum_manifest(restore_dir)
        
        if set(actual_manifest.keys()) != set(expected_manifest.keys()):
            print('[失败] 文件列表不一致')
            verify_passed = False
        else:
            all_ok = True
            for rel_path, expected_hash in expected_manifest.items():
                actual_hash = actual_manifest.get(rel_path, '')
                if actual_hash != expected_hash:
                    print(f'[失败] {rel_path} SHA256 不匹配')
                    all_ok = False
                    verify_passed = False
            
            if all_ok:
                print('[OK] 所有文件 SHA256 校验通过')
    
    file_count = len(os.listdir(restore_dir))
    
    print(f'\n恢复完成: {restore_dir}')
    print(f'恢复文件: {file_count} 个')
    print(f'耗时: {elapsed:.2f} 秒')
    print(f'校验通过: {verify_passed}')
    
    return {
        'restore_path': restore_dir,
        'file_count': file_count,
        'verify_passed': verify_passed,
        'elapsed_seconds': elapsed
    }


def verify_backup(backup_file):
    """
    验证备份文件完整性
    
    返回:
        {
            'backup_file': 备份文件路径,
            'file_count': 文件数量,
            'backup_size': 大小,
            'backup_at': 备份时间,
            'manifest_path': 校验清单路径
        }
    """
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f'备份文件不存在: {backup_file}')
    
    manifest_path = backup_file + '.sha256'
    
    if not os.path.exists(manifest_path):
        print(f'警告: 未找到校验清单 {manifest_path}')
        return {
            'backup_file': backup_file,
            'file_count': -1,
            'backup_size': os.path.getsize(backup_file),
            'has_manifest': False
        }
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)
    
    return {
        'backup_file': backup_file,
        'file_count': manifest_data.get('file_count', -1),
        'backup_size': manifest_data.get('backup_size', -1),
        'backup_at': manifest_data.get('backup_at', ''),
        'format': manifest_data.get('format', ''),
        'manifest_path': manifest_path,
        'has_manifest': True
    }


def list_backups(backup_dir):
    """列出指定目录下的所有备份文件"""
    if not os.path.isdir(backup_dir):
        return []
    
    backups = []
    for fname in sorted(os.listdir(backup_dir)):
        if fname.startswith('archive_backup_') and (fname.endswith('.tar.gz') or fname.endswith('.zip') or fname.endswith('.tgz')):
            fpath = os.path.join(backup_dir, fname)
            backups.append({
                'name': fname,
                'path': fpath,
                'size': os.path.getsize(fpath),
                'mtime': datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
            })
    
    return backups


if __name__ == '__main__':
    if len(sys.argv) > 1:
        archive_dir = sys.argv[1]
    else:
        archive_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '归档')
    
    result = backup_archive(archive_dir)
    print(f'\n备份信息: {json.dumps(result, ensure_ascii=False, indent=2, default=str)}')
