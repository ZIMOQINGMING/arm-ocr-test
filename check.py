#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境自检脚本：正式启动前跑一次，检查环境是否就绪。
用法：python3 check.py
全绿就说明可以启动（python3 start.py）；有红项会提示缺什么。
"""
import os, sys, json, subprocess, tempfile, socket

BASE = os.path.dirname(os.path.abspath(__file__))
PTOOL_BIN = os.path.join(BASE, 'poppler工具', 'usr', 'bin')
PTOOL_LIB = os.path.join(BASE, 'poppler工具', 'usr', 'lib64')
TTOOL_BIN = os.path.join(BASE, 'tesseract工具', 'usr', 'bin')
TTOOL_LIB = os.path.join(BASE, 'tesseract工具', 'usr', 'lib64')
TTOOL_DATA = os.path.join(BASE, 'tesseract工具', 'usr', 'share', 'tesseract')
# TESSDATA_PREFIX 必须指向 tessdata 目录本身（tesseract 4.1.1 直接拼 TESSDATA_PREFIX/xxx.traineddata）
TTOOL_TESSDATA = os.path.join(TTOOL_DATA, 'tessdata')

results = []

def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  [OK] ' if ok else '  [失败] ') + name + (('  -> ' + detail) if detail else ''))

print('=' * 50)
print('  环境自检')
print('=' * 50)

# 1. Python 版本
ver = sys.version_info
check('Python 版本', ver >= (3, 6), 'Python %d.%d.%d' % (ver.major, ver.minor, ver.micro))

# 2. 二进制可执行（带 LD_LIBRARY_PATH 和 TESSDATA_PREFIX）
def check_bin(name, exe, libdir, is_tess=False):
    if not os.path.exists(exe):
        check(name + ' 存在', False, '文件不存在：' + exe)
        return
    # U 盘/压缩包传输可能丢可执行位，运行前补上
    if not os.access(exe, os.X_OK):
        try:
            os.chmod(exe, 0o755)
        except Exception:
            pass
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = libdir + ':' + env.get('LD_LIBRARY_PATH', '')
    if is_tess:
        env['TESSDATA_PREFIX'] = TTOOL_TESSDATA
    try:
        # 注意：pdftotext 只认 -v，不认 --version（会把 --version 当文件名打开而报错）
        # tesseract 两种都支持，所以统一用 -v
        r = subprocess.run([exe, '-v'], capture_output=True, env=env, timeout=30)
        first = r.stdout.decode('utf-8', 'ignore').splitlines()
        first = first[0] if first else '(无输出)'
        check(name + ' 可执行', r.returncode == 0, first[:60])
    except Exception as e:
        check(name + ' 可执行', False, str(e))

check_bin('tesseract(OCR)', os.path.join(TTOOL_BIN, 'tesseract'), TTOOL_LIB, is_tess=True)
# pdftotext 的依赖库(libstdc++/freetype/fontconfig/jpeg/png/tiff/nss 等)在 tesseract工具 包里，
# 必须把两个 lib64 都加进搜索路径，纯绿色机才能跑通
check_bin('pdftotext(PDF转文字)', os.path.join(PTOOL_BIN, 'pdftotext'), PTOOL_LIB + ':' + TTOOL_LIB)

# 3. 中文数据
chi = os.path.join(TTOOL_DATA, 'tessdata', 'chi_sim.traineddata')
if os.path.exists(chi):
    check('中文识别数据 chi_sim', os.path.getsize(chi) > 1000000, '%d KB' % (os.path.getsize(chi) // 1024))
else:
    check('中文识别数据 chi_sim', False, '缺失')

# 4a. 全部 poppler 工具
for t in ['pdfinfo', 'pdftoppm', 'pdfseparate', 'pdfimages']:
    if not os.path.exists(os.path.join(PTOOL_BIN, t)):
        check('poppler: %s 缺失' % t, False, 'PDF 处理将失败')

# 4b. xlrd 库（xls 解析）
xlrd_path = os.path.join(BASE, '_libs', 'xlrd', '__init__.py')
check('_libs/xlrd（xls 解析库）', os.path.exists(xlrd_path), '缺失则 xls 不可用' if not os.path.exists(xlrd_path) else '就绪')

# 4c. 形近字容错表
try:
    d = json.load(open(os.path.join(BASE, '形近字表.json'), encoding='utf-8'))
    check('形近字容错表', len(d) > 0, '%d 字' % len(d))
except Exception as e:
    check('形近字容错表', False, str(e))

# 5. 归档目录可写
arch = os.path.join(BASE, '归档')
os.makedirs(arch, exist_ok=True)
check('归档目录可写', os.access(arch, os.W_OK), arch)

# 6. 端口 8765 可用
try:
    s = socket.socket()
    s.bind(('127.0.0.1', 8765))
    s.close()
    check('端口 8765 可用', True)
except Exception:
    check('端口 8765 可用', False, '被占用或受限')

# 7. 中文路径/文件名
try:
    tmp = tempfile.mkdtemp(prefix='自检_')
    fp = os.path.join(tmp, '测试文件.txt')
    open(fp, 'w', encoding='utf-8').write('测试')
    os.remove(fp)
    os.rmdir(tmp)
    check('中文路径/文件名', True)
except Exception as e:
    check('中文路径/文件名', False, str(e))

# 8. 磁盘剩余空间（OCR 中间产物需要空间）
import shutil
free = shutil.disk_usage(BASE).free
check('磁盘剩余空间', free > 500 * 1024 * 1024, '%.1f GB' % (free / 1024 / 1024 / 1024))

# 9. 系统编码（需 UTF-8，否则中文乱码）
import locale
enc = locale.getpreferredencoding()
check('系统编码 UTF-8', enc.lower().replace('-', '') in ('utf8', 'utf_8'), enc)

print('-' * 50)
fails = [r for r in results if not r[1]]
if fails:
    print('结果：%d 项里 %d 项失败，请把上面失败项发给技术人员：' % (len(results), len(fails)))
    for name, ok, detail in fails:
        print('   ✗ ' + name + ': ' + detail)
else:
    print('结果：全部 %d 项检查通过，可以启动。' % len(results))
    print('启动命令：python3 start.py')
print('=' * 50)
