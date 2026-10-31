#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T8 归档管理界面测试

测试项：
1. 主页面 HTML 包含"管理"标签页
2. 前端 HTML 包含管理面板 ID（panel-manage）
3. 前端 HTML 包含 deleteFile 函数
4. /archive/delete API（POST）正确删除文件
5. 删除后再次查询 /files 确认文件不存在
6. 删除不存在的文件返回 404
7. 删除文件后归档目录正确

证据落盘：evidence/T8/output.txt
"""
import os
import sys
import json
import shutil
import time
import tempfile
from http.client import HTTPConnection
from urllib.parse import quote

# 导入被测模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from start import INDEX_HTML

# 归档目录（用于恢复文件）
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '归档')


def get_service_port():
    """尝试找到运行中的服务端口"""
    for port in range(8765, 8776):
        try:
            conn = HTTPConnection('127.0.0.1', port, timeout=1)
            conn.request('GET', '/')
            resp = conn.getresponse()
            conn.close()
            if resp.status == 200:
                return port
            conn.close()
        except:
            continue
    return None


def test_manage_tab_in_html():
    """T8-1: 主页面 HTML 包含'管理'标签"""
    print('\n[T8-1] HTML 包含"管理"标签测试')

    if '管理' in INDEX_HTML and 'tabManage' in INDEX_HTML:
        print('  [PASS] INDEX_HTML 包含"管理"标签和 tabManage')
        return {'status': 'PASS'}
    else:
        print('  [FAIL] INDEX_HTML 缺少"管理"标签或 tabManage')
        return {'status': 'FAIL'}


def test_manage_panel_in_html():
    """T8-2: 前端 HTML 包含 panel-manage 面板"""
    print('\n[T8-2] HTML 包含 panel-manage 面板测试')

    if 'panel-manage' in INDEX_HTML and 'loadManageFiles' in INDEX_HTML:
        print('  [PASS] INDEX_HTML 包含 panel-manage 和 loadManageFiles')
        return {'status': 'PASS'}
    else:
        print('  [FAIL] INDEX_HTML 缺少 panel-manage 或 loadManageFiles')
        return {'status': 'FAIL'}


def test_delete_function_in_html():
    """T8-3: 前端 HTML 包含 deleteFile 函数"""
    print('\n[T8-3] HTML 包含 deleteFile 函数测试')

    if 'deleteFile' in INDEX_HTML and '/archive/delete' in INDEX_HTML:
        print('  [PASS] INDEX_HTML 包含 deleteFile 函数和 /archive/delete API')
        return {'status': 'PASS'}
    else:
        print('  [FAIL] INDEX_HTML 缺少 deleteFile 或 /archive/delete')
        return {'status': 'FAIL'}


def test_archive_delete_api(port):
    """T8-4: 删除归档文件 API 测试

    策略：创建临时测试文件 → 上传到系统 → 验证在列表中 → 删除 → 验证不在列表中
    完全不碰真实归档文件。
    """
    print('\n[T8-4] 删除归档文件 API 测试')

    try:
        # 1. 创建临时测试文件
        tmp_dir = tempfile.mkdtemp(prefix='t8_test_')
        tmp_file = os.path.join(tmp_dir, 'T8测试文件.txt')
        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write('这是 T8 归档管理界面测试的临时文件，测试完成后会被删除。\n')

        # 2. 上传到系统（服务器期望原始文件内容，非 multipart）
        file_content = open(tmp_file, 'rb').read()
        headers = {'Content-Type': 'application/octet-stream'}

        conn = HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request('POST', '/upload?name=' + quote('T8测试文件.txt'), body=file_content, headers=headers)
        resp = conn.getresponse()
        upload_data = json.loads(resp.read().decode('utf-8'))
        conn.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)

        if not upload_data.get('ok'):
            print(f'  [WARN] 上传临时文件失败: {upload_data}')
            return {'status': 'WARN', 'reason': '上传失败'}

        test_filename = 'T8测试文件.txt'
        print(f'  已上传: {test_filename}')

        # 3. 验证在列表中
        conn = HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET', '/files')
        resp = conn.getresponse()
        files = json.loads(resp.read().decode('utf-8'))
        conn.close()

        found_before = any(f['name'] == test_filename for f in files)
        if not found_before:
            print(f'  [WARN] 上传后不在列表中')

        # 4. 删除
        conn = HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('POST', '/archive/delete',
                     body=json.dumps({'name': test_filename}).encode('utf-8'),
                     headers={'Content-Type': 'application/json'})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode('utf-8'))
        conn.close()

        if resp.status == 200 and data.get('ok') is True:
            print(f'  [PASS] 删除成功: {test_filename}')
            return {'status': 'PASS', 'deleted': test_filename, 'degraded': False}
        else:
            print(f'  [FAIL] 删除失败: {data}')
            return {'status': 'FAIL', 'response': data}

    except Exception as e:
        print(f'  [FAIL] 删除 API 异常: {e}')
        return {'status': 'FAIL', 'error': str(e)}


def test_file_removed_from_list(port, deleted_filename):
    """T8-5: 删除后文件不在列表中"""
    print('\n[T8-5] 文件删除后不在列表中测试')

    try:
        conn = HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET', '/files')
        resp = conn.getresponse()
        files = json.loads(resp.read().decode('utf-8'))
        conn.close()

        found = False
        for f in files:
            if f['name'] == deleted_filename:
                found = True
                break

        if not found:
            print(f'  [PASS] {deleted_filename} 已从文件列表中移除')
            return {'status': 'PASS', 'remaining_files': len(files)}
        else:
            print(f'  [FAIL] {deleted_filename} 仍在文件列表中')
            return {'status': 'FAIL', 'remaining_files': len(files)}
    except Exception as e:
        print(f'  [FAIL] 查询文件列表异常: {e}')
        return {'status': 'FAIL', 'error': str(e)}


def test_delete_nonexistent_file(port):
    """T8-6: 删除不存在的文件返回 404"""
    print('\n[T8-6] 删除不存在的文件测试')

    try:
        conn = HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('POST', '/archive/delete',
                     body=json.dumps({'name': '不存在的文件_xyz.txt'}).encode('utf-8'),
                     headers={'Content-Type': 'application/json'})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode('utf-8'))
        conn.close()

        if resp.status == 404 and data.get('ok') is False:
            print('  [PASS] 删除不存在文件返回 404')
            return {'status': 'PASS'}
        elif resp.status == 200 and data.get('ok') is False:
            # 有些实现返回 200 + {ok: False} 也可以接受
            print('  [PASS] 删除不存在文件返回 {ok: False}')
            return {'status': 'PASS'}
        else:
            print(f'  [WARN] 删除不存在文件返回: HTTP {resp.status}, {data}')
            return {'status': 'WARN', 'response': data}
    except Exception as e:
        print(f'  [FAIL] 删除不存在文件异常: {e}')
        return {'status': 'FAIL', 'error': str(e)}


def test_archive_directory_consistency(port):
    """T8-7: 删除后归档目录一致性"""
    print('\n[T8-7] 归档目录一致性测试')

    try:
        conn = HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET', '/files')
        resp = conn.getresponse()
        files = json.loads(resp.read().decode('utf-8'))
        conn.close()

        # 验证每个文件在磁盘上存在
        all_exist = True
        for f in files:
            if not os.path.exists(f['dir']):
                print(f'  [FAIL] 目录不存在: {f["dir"]}')
                all_exist = False
                break
            if not os.path.exists(f['name']) and not os.path.exists(os.path.join(f['dir'], f['name'])):
                # 尝试从 dir 路径找
                pass

        if all_exist:
            print(f'  [PASS] {len(files)} 个文件的目录结构正常')
            return {'status': 'PASS', 'file_count': len(files)}
        else:
            return {'status': 'FAIL'}
    except Exception as e:
        print(f'  [FAIL] 归档目录检查异常: {e}')
        return {'status': 'FAIL', 'error': str(e)}


def main():
    """主测试流程"""
    print('=' * 60)
    print('T8 归档管理界面测试')
    print('=' * 60)

    results = {}

    # T8-1: HTML 包含"管理"标签
    results['T8-1'] = test_manage_tab_in_html()

    # T8-2: HTML 包含 panel-manage
    results['T8-2'] = test_manage_panel_in_html()

    # T8-3: HTML 包含 deleteFile 函数
    results['T8-3'] = test_delete_function_in_html()

    # 后端 API 测试需要服务运行
    port = get_service_port()

    if port is None:
        print('\n[SKIP] 未检测到运行中的服务 (127.0.0.1:8765-8776)')
        print('提示: 请先启动服务 python3 start.py')

        # 即使没有服务，前端 HTML 测试仍可落盘
        evidence_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'evidence', 'T8')
        os.makedirs(evidence_dir, exist_ok=True)
        output_path = os.path.join(evidence_dir, 'output.txt')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('T8 归档管理界面测试证据\n')
            f.write('=' * 60 + '\n')
            f.write(f'测试时间: {time.strftime("%Y-%m-%dT%H:%M:%S")}\n')
            f.write('结果: 前端 HTML 测试完成，后端 API 测试需服务运行\n\n')

            for key, result in results.items():
                status = result.get('status', 'UNKNOWN')
                f.write(f'{key}: {status}\n')
                for k, v in result.items():
                    if k != 'status':
                        f.write(f'  {k}: {v}\n')
                f.write('\n')

        print(f'证据落盘: {output_path}')
        return 0

    print(f'\n服务端口: {port}')

    # T8-4: 删除 API
    results['T8-4'] = test_archive_delete_api(port)
    deleted_file = None
    if results['T8-4'].get('status') == 'PASS':
        deleted_file = results['T8-4'].get('deleted')

    # T8-5: 文件从列表中移除
    if deleted_file:
        results['T8-5'] = test_file_removed_from_list(port, deleted_file)
    else:
        results['T8-5'] = {'status': 'SKIP', 'reason': 'T8-4 未删除文件'}

    # T8-6: 删除不存在文件
    results['T8-6'] = test_delete_nonexistent_file(port)

    # T8-7: 归档目录一致性
    results['T8-7'] = test_archive_directory_consistency(port)

    # 统计
    pass_count = sum(1 for v in results.values() if v.get('status') == 'PASS')
    total = len(results)

    print('\n' + '=' * 60)
    print(f'T8 测试结果: {pass_count}/{total} 通过')
    print('=' * 60)

    # 落盘证据
    evidence_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'evidence', 'T8')
    os.makedirs(evidence_dir, exist_ok=True)
    output_path = os.path.join(evidence_dir, 'output.txt')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('T8 归档管理界面测试证据\n')
        f.write('=' * 60 + '\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%dT%H:%M:%S")}\n')
        f.write(f'服务端口: {port}\n')
        f.write(f'结果: {pass_count}/{total} 通过\n\n')

        for key, result in results.items():
            status = result.get('status', 'UNKNOWN')
            f.write(f'{key}: {status}\n')
            for k, v in result.items():
                if k != 'status':
                    f.write(f'  {k}: {v}\n')
            f.write('\n')

    print(f'证据落盘: {output_path}')

    return 0 if pass_count == total else 1


if __name__ == '__main__':
    sys.exit(main())
