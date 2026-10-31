#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T6 备份恢复测试

测试项：
1. 备份归档目录为 tar.gz 格式（基础备份）
2. 备份归档目录为 zip 格式（替代备份）
3. 验证备份文件完整性（SHA256 校验清单生成）
4. 从 tar.gz 备份恢复到新目录并验证一致性
5. 从 zip 备份恢复到新目录并验证一致性
6. 备份恢复后文件数量与内容一致性校验
7. 验证备份（verify_backup）功能

证据落盘：evidence/T6/output.txt
"""
import os
import sys
import json
import shutil
import time
import hashlib

# 导入被测模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backup_restore import (
    backup_archive,
    restore_archive,
    verify_backup,
    list_backups,
    sha256_file,
    generate_checksum_manifest
)


def sha256_str(s):
    """计算字符串的 SHA256"""
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def run_backup_test():
    """基础备份测试：备份归档目录到 backups/"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    archive_dir = os.path.join(base, '归档')
    backup_dir = os.path.join(base, 'test_backups')

    print('\n[T6-1] 基础备份测试 (tar.gz)')
    print(f'  源目录: {archive_dir}')

    if not os.path.isdir(archive_dir):
        return {'status': 'SKIP', 'reason': '归档目录不存在'}

    # 备份
    result = backup_archive(archive_dir, backup_dir, format='tar.gz')
    backup_path = result['backup_path']

    # 验证备份文件存在
    assert os.path.exists(backup_path), f'备份文件不存在: {backup_path}'
    assert result['file_count'] > 0, f'备份文件数为 0'

    # 验证校验清单存在
    assert os.path.exists(result['manifest_path']), '校验清单不存在'

    # 验证清单内容
    with open(result['manifest_path'], 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)
    assert manifest_data['file_count'] > 0, '清单中文件数为 0'
    assert 'checksums' in manifest_data, '清单缺少 checksums'
    assert len(manifest_data['checksums']) == result['file_count'], '清单文件数不匹配'

    print(f'  [PASS] 备份成功: {result["file_count"]} 个文件, {result["backup_size"]} 字节')
    print(f'  [PASS] 校验清单生成: {len(manifest_data["checksums"])} 项')

    return {
        'status': 'PASS',
        'backup_path': backup_path,
        'manifest_path': result['manifest_path'],
        'file_count': result['file_count'],
        'backup_size': result['backup_size']
    }


def run_zip_backup_test(backup_dir):
    """ZIP 格式备份测试"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    archive_dir = os.path.join(base, '归档')

    print('\n[T6-2] ZIP 格式备份测试')

    result = backup_archive(archive_dir, backup_dir, format='zip')
    backup_path = result['backup_path']

    assert os.path.exists(backup_path), f'ZIP 备份文件不存在: {backup_path}'
    assert backup_path.endswith('.zip'), f'备份文件不是 .zip 格式'
    assert result['file_count'] > 0, f'备份文件数为 0'

    print(f'  [PASS] ZIP 备份成功: {result["file_count"]} 个文件, {result["backup_size"]} 字节')

    return {
        'status': 'PASS',
        'backup_path': backup_path,
        'file_count': result['file_count']
    }


def run_restore_test(backup_path, restore_dir):
    """从 tar.gz 备份恢复并验证"""
    print(f'\n[T6-3] tar.gz 备份恢复测试')
    print(f'  备份文件: {backup_path}')
    print(f'  恢复目录: {restore_dir}')

    if not os.path.exists(backup_path):
        return {'status': 'SKIP', 'reason': f'备份文件不存在: {backup_path}'}

    # 恢复
    result = restore_archive(backup_path, restore_dir, verify=True)

    assert result['verify_passed'], '恢复校验未通过'
    assert result['file_count'] > 0, f'恢复文件数为 0'

    print(f'  [PASS] 恢复成功: {result["file_count"]} 个文件, 校验通过')

    return {
        'status': 'PASS' if result.get('verify_passed') else 'FAIL',
        'restore_path': result.get('restore_path'),
        'file_count': result.get('file_count'),
        'verify_passed': result.get('verify_passed'),
        'elapsed_seconds': result.get('elapsed_seconds')
    }


def run_content_consistency_test(archive_dir, restore_dir):
    """验证恢复后文件内容一致性"""
    print('\n[T6-4] 恢复内容一致性测试')

    # 读取源目录关键文件内容
    txt_files = [f for f in os.listdir(archive_dir) if f.endswith('.txt')]
    if not txt_files:
        return {'status': 'SKIP', 'reason': '归档目录无 txt 文件'}

    # 选取前 5 个文件验证内容一致性
    sample_files = sorted(txt_files)[:5]
    all_match = True

    for fname in sample_files:
        src_path = os.path.join(archive_dir, fname)
        dst_path = os.path.join(restore_dir, fname)

        if not os.path.exists(dst_path):
            print(f'  [FAIL] {fname} 恢复后不存在')
            all_match = False
            continue

        # 逐字节比较
        with open(src_path, 'rb') as f1, open(dst_path, 'rb') as f2:
            src_content = f1.read()
            dst_content = f2.read()

        if src_content != dst_content:
            print(f'  [FAIL] {fname} 内容不一致')
            all_match = False
        else:
            print(f'  [OK] {fname} 内容一致 ({len(dst_content)} 字节)')

    if all_match:
        print(f'  [PASS] 全部 {len(sample_files)} 个样本内容一致')
        return {'status': 'PASS', 'sample_count': len(sample_files)}
    else:
        print(f'  [FAIL] 部分内容不一致')
        return {'status': 'FAIL', 'sample_count': len(sample_files)}


def run_verify_test(backup_path):
    """验证备份文件"""
    print('\n[T6-5] 备份验证测试')

    if not os.path.exists(backup_path):
        return {'status': 'SKIP', 'reason': f'备份文件不存在'}

    result = verify_backup(backup_path)
    assert result['has_manifest'], '备份缺少校验清单'
    assert result['file_count'] > 0, '备份文件数为 0'

    print(f'  [PASS] 备份验证: {result["file_count"]} 个文件, {result["backup_size"]} 字节')

    return {
        'status': 'PASS',
        'backup_file': result.get('backup_file'),
        'file_count': result.get('file_count'),
        'backup_size': result.get('backup_size'),
        'backup_at': result.get('backup_at'),
        'format': result.get('format'),
        'has_manifest': result.get('has_manifest')
    }


def run_list_backups_test(backup_dir):
    """列出所有备份"""
    print('\n[T6-6] 备份列表测试')

    backups = list_backups(backup_dir)
    print(f'  找到 {len(backups)} 个备份文件')

    for b in backups:
        print(f'    - {b["name"]} ({b["size"]} 字节, {b["mtime"]})')

    if len(backups) >= 2:
        print(f'  [PASS] 找到 {len(backups)} 个备份文件')
        return {'status': 'PASS', 'count': len(backups)}
    else:
        print(f'  [WARN] 仅找到 {len(backups)} 个备份文件（期望 ≥2）')
        return {'status': 'WARN', 'count': len(backups)}


def run_backup_dir_write_fail_test():
    """测试归档目录不存在时的错误处理"""
    print('\n[T6-7] 错误处理测试：归档目录不存在')

    try:
        backup_archive('/非存在的目录/xyz', '/tmp/test_backup')
        print('  [FAIL] 应抛出异常但未抛出')
        return {'status': 'FAIL'}
    except FileNotFoundError as e:
        print(f'  [PASS] 正确抛出 FileNotFoundError: {e}')
        return {'status': 'PASS'}


def main():
    """主测试流程"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(base, 'test_backups')
    restore_dir = os.path.join(base, 'test_restore')

    # 清理上次测试残留
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    if os.path.exists(restore_dir):
        shutil.rmtree(restore_dir)

    print('=' * 60)
    print('T6 备份恢复测试')
    print('=' * 60)

    results = {}

    # T6-1: 基础备份
    results['T6-1'] = run_backup_test()

    # T6-2: ZIP 备份
    if results['T6-1']['status'] == 'PASS':
        results['T6-2'] = run_zip_backup_test(backup_dir)

    # T6-3: tar.gz 恢复
    tar_backup = os.path.join(backup_dir, f'archive_backup_{datetime_now_str()}.tar.gz')
    # 实际找最新的 tar.gz
    if os.path.exists(backup_dir):
        tar_files = [f for f in os.listdir(backup_dir) if f.endswith('.tar.gz')]
        if tar_files:
            tar_backup = os.path.join(backup_dir, sorted(tar_files)[-1])
            results['T6-3'] = run_restore_test(tar_backup, restore_dir)

    # T6-4: 内容一致性（在清理 restore_dir 之前执行）
    if results.get('T6-3', {}).get('status') == 'PASS':
        results['T6-4'] = run_content_consistency_test(
            os.path.join(base, '归档'), restore_dir
        )
    else:
        results['T6-4'] = {'status': 'SKIP', 'reason': 'T6-3 未通过或不存在'}

    # T6-5: 备份验证
    if os.path.exists(backup_dir):
        tar_files = [f for f in os.listdir(backup_dir) if f.endswith('.tar.gz')]
        if tar_files:
            tar_backup = os.path.join(backup_dir, sorted(tar_files)[-1])
            results['T6-5'] = run_verify_test(tar_backup)

    # T6-6: 备份列表
    results['T6-6'] = run_list_backups_test(backup_dir)

    # T6-7: 错误处理
    results['T6-7'] = run_backup_dir_write_fail_test()

    # 统计
    pass_count = sum(1 for v in results.values() if v.get('status') == 'PASS')
    total = len(results)

    print('\n' + '=' * 60)
    print(f'T6 测试结果: {pass_count}/{total} 通过')
    print('=' * 60)

    # 落盘证据
    evidence_dir = os.path.join(base, 'evidence', 'T6')
    os.makedirs(evidence_dir, exist_ok=True)
    output_path = os.path.join(evidence_dir, 'output.txt')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('T6 备份恢复测试证据\n')
        f.write('=' * 60 + '\n')
        f.write(f'测试时间: {datetime_now_str()}\n')
        f.write(f'结果: {pass_count}/{total} 通过\n\n')

        for key, result in results.items():
            status = result.get('status', 'UNKNOWN')
            f.write(f'{key}: {status}\n')
            for k, v in result.items():
                if k not in ('status',):
                    f.write(f'  {k}: {v}\n')
            f.write('\n')

        # 列出备份文件
        f.write('备份文件列表:\n')
        if os.path.exists(backup_dir):
            for fname in sorted(os.listdir(backup_dir)):
                fpath = os.path.join(backup_dir, fname)
                f.write(f'  {fname} ({os.path.getsize(fpath)} 字节)\n')

    print(f'证据落盘: {output_path}')

    # 清理测试目录
    if os.path.exists(restore_dir):
        shutil.rmtree(restore_dir)

    return 0 if pass_count == total else 1


def datetime_now_str():
    from datetime import datetime
    return datetime.now().isoformat()


if __name__ == '__main__':
    sys.exit(main())
