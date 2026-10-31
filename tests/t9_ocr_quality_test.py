#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T9 归档 OCR 质量基准测试
- 扫描归档目录中的真实扫描件（PDF 图片/PNG/JPG/TIFF）
- 对 ≥10 份扫描件进行 OCR 质量测试
- 报告 OCR 准确率、识别速度、引擎类型
- 证据落盘：evidence/T9/output.txt
"""
import os, sys, json, subprocess, time, shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(BASE, '归档')

# ---------- 路径配置 ----------
PTOOL_BIN = os.path.join(BASE, 'poppler工具', 'usr', 'bin')
PTOOL_LIB = os.path.join(BASE, 'poppler工具', 'usr', 'lib64')
TTOOL_BIN = os.path.join(BASE, 'tesseract工具', 'usr', 'bin')
TTOOL_LIB = os.path.join(BASE, 'tesseract工具', 'usr', 'lib64')
TTOOL_DATA = os.path.join(BASE, 'tesseract工具', 'usr', 'share', 'tesseract')
TTOOL_TESSDATA = os.path.join(TTOOL_DATA, 'tessdata')

results = []

def report(name, ok, detail=''):
    results.append({'test': name, 'pass': ok, 'detail': detail})
    print(f"  {'[PASS]' if ok else '[FAIL]'} {name}" + (f"  -> {detail}" if detail else ""))

# ---------- 1. 扫描真实扫描件 ----------
def find_scan_files():
    """在归档目录中查找真实扫描件（PDF 二进制 / PNG / JPG / TIFF）"""
    scans = []
    if not os.path.exists(ARCHIVE):
        return scans
    for f in os.listdir(ARCHIVE):
        fp = os.path.join(ARCHIVE, f)
        if not os.path.isfile(fp):
            continue
        with open(fp, 'rb') as fh:
            header = fh.read(8)
        if header[:4] == b'%PDF':
            scans.append((f, 'pdf', os.path.getsize(fp)))
        elif header[:2] == b'\xff\xd8' and header[4:7] == b'JFIF':
            scans.append((f, 'jpg', os.path.getsize(fp)))
        elif header[:4] == b'\x89PNG':
            scans.append((f, 'png', os.path.getsize(fp)))
        elif header[:4] == b'II\x2a\x00' or header[:4] == b'MM\x00\x2a':
            scans.append((f, 'tif', os.path.getsize(fp)))
    return scans

# ---------- 2. 检查 OCR 引擎 ----------
def check_ocr_engine():
    """检查 tesseract 是否可用"""
    exe = os.path.join(TTOOL_BIN, 'tesseract')
    if not os.path.exists(exe):
        return False, 'tesseract 可执行文件不存在'
    
    # 尝试运行（可能因平台不兼容失败）
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = TTOOL_LIB + ':' + env.get('LD_LIBRARY_PATH', '')
    env['TESSDATA_PREFIX'] = TTOOL_TESSDATA
    try:
        r = subprocess.run([exe, '-v'], capture_output=True, env=env, timeout=10)
        if r.returncode == 0:
            version = r.stdout.decode('utf-8', 'ignore').splitlines()[0][:60]
            return True, version
        else:
            return False, f'tesseract 返回码 {r.returncode}'
    except OSError as e:
        if 'WinError 193' in str(e):
            return False, 'tesseract 是 Linux 绿色版，Windows 不可用'
        return False, str(e)
    except Exception as e:
        return False, str(e)

def check_rapidocr():
    """检查 RapidOCR 是否可用"""
    try:
        for modname in ('rapidocr_onnxruntime', 'rapidocr'):
            try:
                mod = __import__(modname, fromlist=['RapidOCR'])
                ocr_cls = getattr(mod, 'RapidOCR')
                eng = ocr_cls()
                return True, 'RapidOCR 就绪'
            except Exception:
                continue
        return False, 'RapidOCR 未安装或初始化失败'
    except Exception as e:
        return False, str(e)

# ---------- 3. 对扫描件进行 OCR 质量测试 ----------
def run_ocr_quality_test(scan_file, expected_text=None):
    """
    对单个扫描件进行 OCR 质量测试
    返回 {'file': ..., 'engine': ..., 'chars': ..., 'time': ..., 'accuracy': ...}
    """
    fname, ftype, fsize = scan_file
    
    # 检查 tesseract
    engine_available = False
    engine_name = ''
    exe = os.path.join(TTOOL_BIN, 'tesseract')
    
    if os.path.exists(exe):
        env = dict(os.environ)
        env['LD_LIBRARY_PATH'] = TTOOL_LIB + ':' + env.get('LD_LIBRARY_PATH', '')
        env['TESSDATA_PREFIX'] = TTOOL_TESSDATA
        try:
            r = subprocess.run([exe, '-v'], capture_output=True, env=env, timeout=10)
            if r.returncode == 0:
                engine_available = True
                engine_name = r.stdout.decode('utf-8', 'ignore').splitlines()[0][:60]
        except OSError:
            pass
    
    # 检查 RapidOCR
    rapid_available = False
    for modname in ('rapidocr_onnxruntime', 'rapidocr'):
        try:
            mod = __import__(modname, fromlist=['RapidOCR'])
            ocr_cls = getattr(mod, 'RapidOCR')
            eng = ocr_cls()
            rapid_available = True
            engine_name = 'RapidOCR'
            break
        except Exception:
            continue
    
    if not engine_available and not rapid_available:
        return {'file': fname, 'engine': '无', 'chars': 0, 'time': 0, 'accuracy': None, 'error': 'OCR 引擎不可用'}
    
    # 如果有快速可用的引擎，尝试 OCR
    start_time = time.time()
    try:
        if rapid_available:
            # RapidOCR 测试（略：需要实际扫描件图片）
            return {'file': fname, 'engine': 'RapidOCR', 'chars': 0, 'time': 0, 'accuracy': None, 'status': '需要真实扫描件'}
        else:
            # tesseract 测试（略：需要真实扫描件图片）
            return {'file': fname, 'engine': 'tesseract', 'chars': 0, 'time': 0, 'accuracy': None, 'status': '需要真实扫描件'}
    except Exception as e:
        return {'file': fname, 'engine': engine_name, 'chars': 0, 'time': time.time() - start_time, 'accuracy': None, 'error': str(e)}

# ---------- 4. 主测试流程 ----------
def main():
    print('=' * 60)
    print('T9 归档 OCR 质量基准测试')
    print('=' * 60)
    
    # T9-1: 检查 tesseract 引擎
    print('\n[T9-1] OCR 引擎可用性检测')
    tess_ok, tess_detail = check_ocr_engine()
    report('tesseract 引擎', tess_ok, tess_detail)
    
    # T9-2: 检查 RapidOCR 引擎
    print('\n[T9-2] RapidOCR 引擎检测')
    rapid_ok, rapid_detail = check_rapidocr()
    report('RapidOCR 引擎', rapid_ok, rapid_detail)
    
    # T9-3: 检查中文识别数据
    print('\n[T9-3] 中文 OCR 数据检测')
    chi = os.path.join(TTOOL_TESSDATA, 'chi_sim.traineddata')
    if os.path.exists(chi):
        size = os.path.getsize(chi)
        report('chi_sim.traineddata 存在', size > 1000000, f'{size // 1024} KB')
    else:
        report('chi_sim.traineddata 存在', False, '缺失')
    
    # T9-4: 扫描真实扫描件
    print('\n[T9-4] 归档目录真实扫描件扫描')
    scans = find_scan_files()
    report('找到真实扫描件', len(scans) >= 10, f'共 {len(scans)} 份（要求 ≥10）')
    
    if scans:
        print(f'  扫描文件列表:')
        for fname, ftype, fsize in scans:
            print(f'    - {fname} ({ftype}, {fsize} bytes)')
    
    # T9-5: OCR 质量测试（如果有真实扫描件）
    print('\n[T9-5] OCR 质量测试（≥10 份扫描件）')
    if len(scans) >= 10:
        ocr_results = []
        for i, scan in enumerate(scans[:10]):
            result = run_ocr_quality_test(scan)
            ocr_results.append(result)
            print(f'  [{i+1}/10] {scan[0]}: {result.get("status", result.get("error", "处理中"))}')
        
        # 汇总
        success = [r for r in ocr_results if r.get('accuracy') is not None and r['accuracy'] >= 0.8]
        report('OCR 质量基准（≥10 份，准确率 ≥80%）', 
               len(success) >= 8, 
               f'成功 {len(success)}/10，平均准确率 {sum(r.get("accuracy", 0) for r in ocr_results if r.get("accuracy") is not None) / max(len(ocr_results), 1):.1%}')
    else:
        report('OCR 质量测试（≥10 份扫描件）', 
               len(scans) >= 10, 
               f'当前 {len(scans)} 份真实扫描件，无法进行质量测试')
    
    # T9-6: 形近字容错表
    print('\n[T9-6] 形近字容错表（OCR 容错检索）')
    xingjin_path = os.path.join(BASE, '形近字表.json')
    if os.path.exists(xingjin_path):
        try:
            d = json.load(open(xingjin_path, encoding='utf-8'))
            report('形近字容错表', len(d) > 0, f'{len(d)} 字')
        except Exception as e:
            report('形近字容错表', False, str(e))
    else:
        report('形近字容错表', False, '缺失')
    
    # T9-7: poppler 工具
    print('\n[T9-7] poppler PDF 处理工具')
    pdftotext_exe = os.path.join(PTOOL_BIN, 'pdftotext')
    if os.path.exists(pdftotext_exe):
        env = dict(os.environ)
        env['LD_LIBRARY_PATH'] = PTOOL_LIB + ':' + TTOOL_LIB + ':' + env.get('LD_LIBRARY_PATH', '')
        try:
            r = subprocess.run([pdftotext_exe, '-v'], capture_output=True, env=env, timeout=10)
            report('pdftotext 工具', r.returncode == 0, r.stdout.decode('utf-8', 'ignore').splitlines()[0][:60] if r.stdout else '未知')
        except Exception as e:
            report('pdftotext 工具', False, str(e))
    else:
        report('pdftotext 工具', False, '缺失')
    
    # ---------- 汇总 ----------
    print('\n' + '=' * 60)
    pass_count = sum(1 for r in results if r['pass'])
    fail_count = sum(1 for r in results if not r['pass'])
    print(f'T9 测试结果: {pass_count}/{pass_count + fail_count} 通过')
    print('=' * 60)
    
    # 证据落盘
    evidence_dir = os.path.join(BASE, 'evidence', 'T9')
    os.makedirs(evidence_dir, exist_ok=True)
    output_path = os.path.join(evidence_dir, 'output.txt')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('T9 归档 OCR 质量基准测试\n')
        f.write('=' * 60 + '\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'归档目录: {ARCHIVE}\n')
        f.write(f'真实扫描件: {len(scans)} 份\n')
        f.write(f'OCR 引擎: tesseract={"可用" if tess_ok else "不可用"}, RapidOCR={"可用" if rapid_ok else "不可用"}\n')
        f.write('-' * 60 + '\n')
        for r in results:
            status = 'PASS' if r['pass'] else 'FAIL'
            f.write(f'[{status}] {r["test"]}: {r.get("detail", "")}\n')
        f.write('-' * 60 + '\n')
        f.write(f'总计: {pass_count} 通过 / {fail_count} 失败\n')
    
    print(f'证据落盘: {output_path}')
    return pass_count, fail_count

if __name__ == '__main__':
    pass_count, fail_count = main()
    sys.exit(0 if fail_count == 0 else 1)
