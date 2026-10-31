#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 云端推送测试 2026-10-31：验证 ECS 中继推送方法（呼和浩特 39.104.106.60）
"""
本地资料归档检索系统（银河麒麟离线机）
- 网页投喂 Word/PDF 文件 → 自动转换 → 逐个归档为 txt → 检索
- 零第三方依赖：只用 Python 标准库 + 自带 poppler 绿色版 + 系统 tesseract
- 启动：python3 start.py   （自动打开浏览器）
"""
import os, sys, json, re, subprocess, zipfile, tempfile, shutil, threading, webbrowser, hashlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
from urllib.parse import urlparse, parse_qs, unquote
from urllib.parse import quote as urlquote

BASE = os.path.dirname(os.path.realpath(__file__))  # realpath 解析软链，避免符号链接启动时定位失效
# 自带纯 Python 库目录（只有 xls 解析用到 xlrd，纯 Python、免安装、不联网）
sys.path.insert(0, os.path.join(BASE, '_libs'))
sys.path.insert(0, BASE)  # 引入 index_db 模块

ARCHIVE = os.path.join(BASE, '归档')
PORT = 8765

# v2 归档结构：files/（原件）+ texts/（文本）+ archive.db（元数据）
V2_ARCHIVE = os.path.join(os.path.expanduser('~'), '检索归档')
V2_FILES = os.path.join(V2_ARCHIVE, 'files')
V2_TEXTS = os.path.join(V2_ARCHIVE, 'texts')

# 归档候选链：优先程序目录；写不进就依次降级到家目录、临时目录。
# 目的：转换/ OCR 往往跑了几分钟甚至几十分钟，绝不能因为最后一步存盘失败让用户白等。
ARCHIVE_DIRS = []
for _d in (ARCHIVE,
           os.path.join(os.path.expanduser('~'), '检索归档'),
           os.path.join(tempfile.gettempdir(), '检索归档')):
    if _d not in ARCHIVE_DIRS:
        ARCHIVE_DIRS.append(_d)

try:
    os.makedirs(ARCHIVE, exist_ok=True)
except Exception:
    pass

# ---------- poppler 绿色版路径（不碰系统 poppler，避免版本冲突）----------
PTOOL_BIN = os.path.join(BASE, 'poppler工具', 'usr', 'bin')
PTOOL_LIB = os.path.join(BASE, 'poppler工具', 'usr', 'lib64')

# ---------- tesseract 绿色版路径（考试机无 rpm，解压即用，不装系统）----------
TTOOL_BIN = os.path.join(BASE, 'tesseract工具', 'usr', 'bin')
TTOOL_LIB = os.path.join(BASE, 'tesseract工具', 'usr', 'lib64')
TTOOL_DATA = os.path.join(BASE, 'tesseract工具', 'usr', 'share', 'tesseract')
# 注意：TESSDATA_PREFIX 必须直接指向 tessdata 目录本身（实测 tesseract 4.1.1 是
# 直接拼 TESSDATA_PREFIX/xxx.traineddata，指向父目录会导致找不到语言包）
TTOOL_TESSDATA = os.path.join(TTOOL_DATA, 'tessdata')

def _ensure_exec(exe):
    """U 盘/压缩包传输可能丢可执行位，运行前补上"""
    if os.path.exists(exe) and not os.access(exe, os.X_OK):
        try:
            os.chmod(exe, 0o755)
        except Exception:
            pass

def _poppler(tool, *args):
    """调用 poppler 工具，优先绿色版，找不到再用系统命令"""
    exe = os.path.join(PTOOL_BIN, tool)
    if os.path.exists(exe):
        _ensure_exec(exe)
        env = dict(os.environ)
        # 注意：poppler 包里只有 libpoppler.so，其余依赖库(libstdc++/freetype/
        # fontconfig/jpeg/png/tiff/nss/openjp2 等)都在 tesseract工具 包里，
        # 必须两个目录都加进 LD_LIBRARY_PATH，否则纯绿色机(无系统依赖)会缺库。
        env['LD_LIBRARY_PATH'] = PTOOL_LIB + ':' + TTOOL_LIB + ':' + env.get('LD_LIBRARY_PATH', '')
        return subprocess.run([exe] + list(args), capture_output=True, env=env)
    return subprocess.run([tool] + list(args), capture_output=True)

def _tesseract(args):
    """调用 tesseract，优先绿色版（自带依赖库+中文数据），找不到再用系统命令"""
    exe = os.path.join(TTOOL_BIN, 'tesseract')
    if os.path.exists(exe):
        _ensure_exec(exe)
        env = dict(os.environ)
        env['LD_LIBRARY_PATH'] = TTOOL_LIB + ':' + env.get('LD_LIBRARY_PATH', '')
        env['TESSDATA_PREFIX'] = TTOOL_TESSDATA
        return subprocess.run([exe] + list(args), capture_output=True, env=env)
    return subprocess.run(['tesseract'] + list(args), capture_output=True)

# ---------- 启动时绿色工具完整性检测 ----------
def _check_green_tools():
    """检测绿色工具是否齐全，缺失项打印告警。不阻断启动。"""
    missing = []
    # poppler 四件套
    for tool in ['pdfinfo', 'pdftoppm', 'pdfseparate', 'pdfimages']:
        p = os.path.join(PTOOL_BIN, tool)
        if not os.path.exists(p):
            missing.append('poppler/%s' % tool)
        else:
            _ensure_exec(p)
    # tesseract
    tess_exe = os.path.join(TTOOL_BIN, 'tesseract')
    if not os.path.exists(tess_exe):
        missing.append('tesseract（绿色版）')
    else:
        _ensure_exec(tess_exe)
    # tessdata 中文包
    tessdata = os.path.join(TTOOL_TESSDATA, 'chi_sim.traineddata')
    if not os.path.exists(tessdata):
        missing.append('tessdata/chi_sim.traineddata（中文 OCR 模型）')
    # xlrd 库
    xlrd_path = os.path.join(BASE, '_libs', 'xlrd', '__init__.py')
    if not os.path.exists(xlrd_path):
        missing.append('_libs/xlrd（xls 解析库）')
    # 形近字表
    conf_path = os.path.join(BASE, '形近字表.json')
    if not os.path.exists(conf_path):
        missing.append('形近字表.json（OCR 容错检索）')
    if missing:
        print('[警告] 以下绿色工具缺失,部分功能将降级或不可用:')
        for m in missing:
            print('  ✗ %s' % m)
        print()
    else:
        print('[OK] 绿色工具链完整。')
    # Python 版本检查（RapidOCR 离线包只支持 3.8）
    if sys.version_info >= (3, 9):
        print('[提示] 当前 Python %d.%d（离线 RapidOCR wheel 仅支持 3.8,不兼容）' % (sys.version_info[0], sys.version_info[1]))
        print('      如需高准确率 OCR,按 03可选升级.txt 编译对应版本的 wheel。')
        print()

_check_green_tools()
del _check_green_tools  # 检测完不需要了

# ---------- 全局索引管理器（T2/T3/T4 核心）----------
DB_MANAGER = None

def _init_index_manager():
    """启动时初始化索引管理器。v2 归档不存在时自动从 v1 扫描重建。"""
    global DB_MANAGER
    try:
        # 优先 v2 归档目录
        for d in (V2_ARCHIVE,) + tuple(ARCHIVE_DIRS):
            if d and os.path.isdir(d):
                db_path = os.path.join(d, 'archive.db')
                if os.path.exists(db_path):
                    from index_db import init_archive_db
                    DB_MANAGER = init_archive_db(d)
                    print('[索引] 已加载索引数据库：%s' % db_path)
                    return
        # 无现有库：尝试从 v1 扫描重建
        print('[索引] 无现有索引库，尝试从归档重建...')
        os.makedirs(V2_FILES, exist_ok=True)
        os.makedirs(V2_TEXTS, exist_ok=True)
        from index_db import init_archive_db, file_sha256
        DB_MANAGER = init_archive_db(V2_ARCHIVE)
        _scan_v1_to_v2()
        print('[索引] 重建完成。')
    except Exception as e:
        print('[警告] 索引初始化失败：%s（将回退到基线文件扫描）' % e)
        DB_MANAGER = None

# 模块加载时自动初始化索引管理器（确保 HTTP 线程也能使用）
try:
    _init_index_manager()
    print(f'[初始化] DB_MANAGER={DB_MANAGER}', flush=True)
except Exception as e:
    print(f'[初始化] 模块级调用失败: {e}', flush=True)
    import traceback
    traceback.print_exc()

def _scan_v1_to_v2():
    """扫描 v1 归档目录，重建 v2 结构 + 索引。"""
    if not DB_MANAGER:
        return
    for d in ARCHIVE_DIRS:
        if not os.path.isdir(d):
            continue
        try:
            for f in os.listdir(d):
                if f.endswith('.txt'):
                    fp = os.path.join(d, f)
                    orig_name = os.path.splitext(f)[0] + '.orig'
                    orig_path = os.path.join(V2_FILES, orig_name)
                    shutil.copy2(fp, orig_path)
                    text_path = os.path.join(V2_TEXTS, f)
                    shutil.copy2(fp, text_path)
                    sha = file_sha256(fp)
                    size = os.path.getsize(fp)
                    DB_MANAGER.add_file(orig_name, f, text_path, orig_path, sha, size, 'v1扫描重建', 0)
        except Exception:
            continue

# ---------- HTTP 线程上限（T7）----------
MAX_HTTP_THREADS = 8
_HTTP_SEM = threading.Semaphore(MAX_HTTP_THREADS)

# ---------- OCR 并发限流（防止几十个扫描件同时 OCR 打满 CPU）----------
OCR_SEM = threading.Semaphore(2)

# ---------- OCR 引擎：优先 RapidOCR（更准），兜底 tesseract ----------
_rapid_engine = None
_rapid_tried = False

def _get_rapid_engine():
    """懒加载 RapidOCR 引擎。
    实测同一份样张：RapidOCR 字准确率 95.51%，tesseract 最高只有 83.62%，
    所以只要装得起就必须优先用它。
    两个 pip 包名都会遇到（rapidocr / rapidocr-onnxruntime），模块名不同，
    只认一个会导致明明装了却加载失败、悄悄退化成低准确率引擎。"""
    global _rapid_engine, _rapid_tried
    if not _rapid_tried:
        _rapid_tried = True
        ocr_cls = None
        for modname in ('rapidocr_onnxruntime', 'rapidocr'):
            try:
                mod = __import__(modname, fromlist=['RapidOCR'])
                ocr_cls = getattr(mod, 'RapidOCR')
                break
            except Exception:
                continue
        try:
            _rapid_engine = ocr_cls() if ocr_cls else None
        except Exception:
            _rapid_engine = None
    return _rapid_engine

def ocr_engine_desc():
    """把实际在用哪个引擎摆到明面上。实测两个引擎准确率差 12 个百分点，
    不能让用户稀里糊涂地用低准确率引擎还以为都一样。"""
    try:
        if _get_rapid_engine():
            return ('RapidOCR　← 推荐。同一份真实扫描件实测：'
                    '"配电箱/互感器/断路器/外形尺寸/元器件安装标准"全部识别正确，接近照抄')
    except Exception:
        pass
    return ('tesseract 备用引擎　← 同一份扫描件实测有较多错字'
            '（如"配电梢""互感咽""断路怖""矿寸""安闭"）。'
            '想要更高准确率，按 03可选升级.txt 装 RapidOCR 离线包')

def ocr_image(img_path, use_rapid=False):
    """OCR 单张图片。use_rapid=True 时用 RapidOCR，失败/未装则用 tesseract。"""
    if use_rapid:
        engine = _get_rapid_engine()
        if engine:
            try:
                with OCR_SEM:
                    result = engine(img_path)
                # RapidOCR 3.x 返回 RapidOCROutput 对象，文本在 .txts 字段（元组）
                # 老版本返回 (result, elapse) 元组，这里兼容两种
                txts = getattr(result, 'txts', None)
                if txts is None:
                    # 兼容 2.x：(result, elapse) -> result 是 [[box, text, score], ...]
                    txts = [item[1] for item in result]
                return '\n'.join(t for t in txts if t)
            except Exception:
                pass
    with OCR_SEM:
        # psm 保持 6 的理由（实测，不是拍脑袋）：
        # 在干净印刷体样本上 psm 11 字准确率 83.62% 确实高于 psm 6 的 77.12%，
        # 但换到真实脏扫描件上，psm 11 会把一句话撕成碎片
        #   （"1. 配电梢在招标工和 / 王 / 里/月 / 单中均要求..."），并额外吐出
        #   "口 至.、主""人人肠"这类噪声块。psm 6 虽有个别错字，但行结构完整、
        #   能读成句子，也更符合"成段"的要求。两者取平衡，留 psm 6。
        r = _tesseract([img_path, 'stdout', '-l', 'chi_sim', '--psm', '6'])
    return r.stdout.decode('utf-8', 'ignore')

# ---------- 转换函数 ----------
def pdf_is_encrypted(p):
    r = _poppler('pdfinfo', p)
    out = r.stdout.decode('utf-8', 'ignore')
    for line in out.split('\n'):
        if line.startswith('Encrypted:'):
            return 'yes' in line.split(':', 1)[1]
    return False

def pdf_pages_text(p):
    """提取 PDF 全文并按页切分（页间是 \f 换页符）"""
    # -layout：保留版面结构。表格类资料（报价单/工程清单）用默认模式会把每个
    # 单元格拆成单独一行，完全没法读；layout 模式能保住"序号 设备名称 单价"这种行。
    r = _poppler('pdftotext', '-layout', p, '-')
    pages = r.stdout.decode('utf-8', 'ignore').split('\f')
    # pdftotext 每页后面都跟一个换页符，最后一页也不例外，
    # split 出来末尾会多一个空元素。不去掉的后果：
    #   ① 页数永远多算一页；
    #   ② 那个空页被判为「扫描页」，白跑一次 300DPI 渲染 + OCR（很慢）。
    while len(pages) > 1 and not pages[-1].strip():
        pages.pop()
    return pages

def is_readable_text_page(text):
    """判断一页是否「文字页」：汉字 >= 20 或 字母数字 >= 20（都是绝对数）。
    只看汉字不行：纯英文页、纯数字表格页一个汉字都没有，会被误判成扫描页，
    白跑 OCR（慢），而且 OCR 用的是 chi_sim，识别英文反而更差。
    只看占比也不行：中英混排的技术标准（GB/T 等）汉字占比天然低，会被误判。
    所以汉字、字母数字各设一个绝对数门槛，取「或」。"""
    if not text:
        return False
    han = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    alnum = sum(1 for c in text if ord(c) < 128 and c.isalnum())
    return han >= 20 or alnum >= 20

def is_garbled_page(text):
    """识别「坏文字层」：有些 PDF（尤其转制/加密过的）字体内缺字符映射，
    提取出来是一堆全角字母数字（ＧＢ／Ｔ→全角）、私用区字符，或"锟斤拷"这类转换残渣。
    这些页看着有字其实全是乱码，必须当扫描页送去 OCR，否则检索到的全是乱码。
    判据：私用区+全角字母数字占整页非空白字符比例 >= 30%（页眉少量乱码不影响正文，不触发）；
    或出现"锟斤拷"/大量"烫"这类典型转换残渣。"""
    chars = [c for c in text if not c.isspace()]
    if len(chars) < 20:
        return False
    priv = sum(1 for c in chars if '\ue000' <= c <= '\uf8ff')
    full = sum(1 for c in chars if '\uff10' <= c <= '\uff19'
               or '\uff21' <= c <= '\uff3a' or '\uff41' <= c <= '\uff5a')
    if (priv + full) / len(chars) >= 0.30:
        return True
    if '锟斤拷' in text or text.count('烫') >= 5:
        return True
    return False

TITLE_PAT = re.compile(r'^(第[一二三四五六七八九十百千零]+[章节条编分讲天]|专题[一二三四五六七八九十百千零]+|[一二三四五六七八九十]+[、.．])')

def merge_paragraphs(text):
    """把 OCR 的一行行文字恢复成段落：句末标点断段、折行拼接、标题行独立成段。
    OCR 丢失了空行/缩进，用「行尾标点 + 标题行」规则重建段落，单栏正文够用。"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    out = []
    buf = ''
    for line in lines:
        # 遇到标题行，或上一个 buf 是标题行，则先断段
        if buf and (TITLE_PAT.match(line) or TITLE_PAT.match(buf)):
            out.append(buf)
            buf = ''
        # 拼接规则：中文字之间直接连（中文不该有空格）；
        # 西文/数字之间补一个空格（表格单元格连起来才读得懂，如"数量 1 LED"）
        if buf and line:
            la, lb = buf[-1], line[0]
            if ord(la) < 128 and ord(lb) < 128 and (la.isalnum() and lb.isalnum()):
                buf = buf + ' ' + line
            else:
                buf = buf + line
        else:
            buf = buf + line
        # 句末标点 = 段尾
        if line.endswith(('。', '！', '？', '；', '：', '」', '）', '’', '"')):
            out.append(re.sub(r'[ \t]{2,}', ' ', buf.strip()))
            buf = ''
    if buf:
        out.append(re.sub(r'[ \t]{2,}', ' ', buf.strip()))
    # layout 模式空格很多，统一压成单空格，避免检索/显示时一串空白
    return '\n'.join(re.sub(r'[ \t]{2,}', ' ', x) for x in out)

def snip(text, kws, width=90):
    """命中内容太长时，只保留关键词前后各 width 个字，前后加省略号。
    合并段落以后一行可能好几百字，全显示反而看不清重点。"""
    if not text:
        return ''
    if len(text) <= width * 2 + 40:
        return text
    pos = -1
    for k in (kws or []):
        i = text.find(k)
        if i >= 0:
            pos = i if pos < 0 else min(pos, i)
    if pos < 0:
        pos = 0
    a = max(0, pos - width)
    b = min(len(text), pos + width)
    return ('…' if a > 0 else '') + text[a:b] + ('…' if b < len(text) else '')

def ocr_pages(p, page_nums):
    """逐页 OCR 指定页码，返回 {页码(1-based): 文本}。300 DPI + PSM 6 提准确率。
    文件级固定引擎：RapidOCR 可用则整文件用它，首图失败则整文件降级 tesseract，
    避免同一份文档半页 RapidOCR、半页 tesseract 导致结果风格不一致。"""
    tmp = tempfile.mkdtemp(prefix='ocr_')
    use_rapid = _get_rapid_engine() is not None
    try:
        import glob
        result = {}
        for pn in page_nums:
            base = os.path.join(tmp, 'p%d' % pn)
            _poppler('pdftoppm', '-r', '300', '-f', str(pn), '-l', str(pn), '-png', p, base)
            txt = ''
            for img in sorted(glob.glob(base + '-*.png')):
                try:
                    txt += ocr_image(img, use_rapid)
                except Exception:
                    use_rapid = False  # RapidOCR 推理失败，整文件降级 tesseract
                    txt += ocr_image(img, False)
                os.remove(img)  # 识别完立即删，控制磁盘占用
            result[pn] = merge_paragraphs(txt)  # 恢复段落
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def convert_pdf(p):
    """逐页分流：可读页用提取文字，扫描/乱码页单独 OCR，按页序拼接。
    避免「全书二选一」导致水印页误判整本、或混合 PDF 整本漏 OCR。"""
    pages = pdf_pages_text(p)
    page_map = {}       # 页索引 -> 文本
    scan_pages = []     # 需要 OCR 的页号（1-based）
    for i, page in enumerate(pages):
        if is_readable_text_page(page) and not is_garbled_page(page):
            # 关键：提取出来的文字页同样要做段落合并。
            # pdftotext 按「视觉行」断行，一句话常被拆成好几行；
            # 不合并的话检索结果只能看到半句话，没法读。
            page_map[i] = merge_paragraphs(page)
        else:
            scan_pages.append(i + 1)
    if scan_pages:
        ocr_result = ocr_pages(p, scan_pages)
        for pn, txt in ocr_result.items():
            page_map[pn - 1] = txt
    out = []
    for i in range(len(pages)):
        if i in page_map:
            out.append(page_map[i])
    text = '\n'.join(out)
    text = strip_headers_footers(text, len(pages))  # 剔除跨页重复的页眉页脚
    if not scan_pages:
        return text, '文字版PDF直接提取'
    if len(scan_pages) >= len(pages):
        return text, '扫描版，已OCR'
    return text, '混合PDF（文字%d页+扫描%d页）' % (len(pages) - len(scan_pages), len(scan_pages))

def docx_text(p):
    r"""提取 docx 文字（保留段落与表格结构）。
    坑1：正则不能写 <w:t[^>]*>，会误匹配 <w:tblPr>/<w:tblW>/<w:tblBorders>
         等表格标签，把整段 XML 当正文（含表格的文档会出一大堆 <w:tbl...> 垃圾）。
         必须写成 <w:t(?:\s[^>]*)?>。
    坑2：换行/制表符不能插在 <w:t> 外面，否则提取时被丢掉，整篇粘成一坨。
         所以要按块切分后逐块提取，再拼分隔符。"""
    z = zipfile.ZipFile(p)
    xml = z.read('word/document.xml').decode('utf-8', 'ignore')
    xml = re.sub(r'<w:br\b[^>]*/?>', '<w:t>\n</w:t>', xml)    # 软换行
    xml = re.sub(r'<w:tab\b[^>]*/?>', '<w:t>\t</w:t>', xml)   # 制表符
    parts = re.split(r'(</w:p>|</w:tc>|</w:tr>)', xml)
    out = []
    i = 0
    while i < len(parts):
        t = ''.join(re.findall(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', parts[i], re.S))
        mark = parts[i + 1] if i + 1 < len(parts) else ''
        if mark == '</w:tc>':
            out.append(t + '\t')     # 单元格之间用制表符
        elif mark:
            out.append(t + '\n')     # 段落结束 / 表格行结束
        else:
            out.append(t)
        i += 2
    text = ''.join(out)
    for a, b in (('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                 ('&quot;', '"'), ('&apos;', "'")):
        text = text.replace(a, b)
    text = re.sub(r'\n\t', '\t', text)        # 单元格内多余换行
    text = re.sub(r'\t{2,}', '\t', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

def _word97_doc(data):
    """按 [MS-DOC] 结构解析 Word 97-2003：CFB -> FIB -> piece table -> 正文。
    为什么不用旧的"utf-16 硬扫整个二进制"：实测对同一份 4.5 万字文档覆盖率只有 41%，
    还会把图片/格式区当成正文吐出六万字符的乱码。这里实测覆盖率 99.37%，零多余字符。"""
    import struct as _st
    from xlrd import compdoc as _cd
    c = _cd.CompDoc(data)
    wd = c.get_named_stream('WordDocument')
    if not wd or len(wd) < 0x200:
        return ''
    t0 = c.get_named_stream('0Table')
    t1 = c.get_named_stream('1Table')
    # FIB
    f_which = bool(_st.unpack('<H', wd[0x0A:0x0C])[0] & 0x0200)  # 1 -> 用 1Table
    ccp_text = _st.unpack('<I', wd[0x50:0x54])[0]                 # FibRgLw.ccpText 正文长度
    fc_clx = _st.unpack('<I', wd[0x01A2:0x01A6])[0]
    lcb_clx = _st.unpack('<I', wd[0x01A6:0x01AA])[0]
    tbl = t1 if (f_which and t1) else t0
    if not tbl or fc_clx <= 0 or lcb_clx <= 0 or fc_clx + lcb_clx > len(tbl):
        return ''
    clx = tbl[fc_clx:fc_clx + lcb_clx]

    # CLX = 若干 Prc + 一个 Pcdt(分片表)
    pieces = []
    i, n = 0, len(clx)
    while i < n:
        if clx[i] == 1:                       # Prc：段落属性，正文用不到
            if i + 3 > n:
                break
            cb = _st.unpack('<h', clx[i + 1:i + 3])[0]
            i += 3 + cb
        elif clx[i] == 2:                     # Pcdt
            if i + 5 > n:
                break
            lcb = _st.unpack('<I', clx[i + 1:i + 5])[0]
            plc = clx[i + 5:i + 5 + lcb]
            if len(plc) > 4:
                cnt = (len(plc) - 4) // 12
                cps = [_st.unpack('<I', plc[4 * k:4 * k + 4])[0] for k in range(cnt + 1)]
                for k in range(cnt):
                    off = 4 * (cnt + 1) + 8 * k
                    if off + 6 > len(plc):
                        break
                    fc = _st.unpack('<I', plc[off + 2:off + 6])[0]
                    comp = bool(fc & 0x40000000)
                    fc &= 0x3FFFFFFF
                    if comp:
                        fc //= 2               # 压缩片：一字符一字节，位置折半
                    pieces.append((fc, cps[k + 1] - cps[k], comp))
            break
        else:
            break
    if not pieces:
        return ''

    buf = []
    left = ccp_text if ccp_text > 0 else 10 ** 9
    for fc, cch, comp in pieces:
        if cch <= 0 or left <= 0:
            continue
        take = min(cch, left)
        try:
            if comp:
                raw = wd[fc:fc + take]
                try:
                    buf.append(raw.decode('cp1252'))
                except Exception:
                    buf.append(raw.decode('latin-1', 'ignore'))
            else:
                buf.append(wd[fc:fc + take * 2].decode('utf-16-le', 'ignore'))
        except Exception:
            pass
        left -= take
    t = ''.join(buf)
    t = t.replace('\r', '\n')      # 段落结束
    t = t.replace('\x07', '\t')    # 表格单元格结束 -> 制表符，保证表格列对得上
    t = t.replace('\x0b', '\n')    # 软换行
    t = re.sub(r'[\x00-\x08\x0c\x0e-\x1f]', '', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()

def doc_text(p):
    t = ''
    try:
        t = _word97_doc(open(p, 'rb').read())
    except Exception:
        t = ''
    return t

def is_zip_file(p):
    """看文件头判断是不是 zip（docx 本质就是 zip，头两个字节是 PK）。
    不能只信扩展名：很多文件是老 .doc 被改成 .docx（或反之），
    只按扩展名分派会直接抛 "File is not a zip file" 崩掉。"""
    try:
        with open(p, 'rb') as f:
            return f.read(2) == b'PK'
    except Exception:
        return False

try:
    import xlrd                      # 纯 Python，随包自带于 _libs，仅老格式 xls 用到
    HAVE_XLRD = True
except Exception:
    xlrd = None
    HAVE_XLRD = False

# ---------- Excel 题库提取 ----------
# 题库型表格必须「一行一条记录」，单元格内容里的换行必须压平，
# 否则一道题会被拆成好几行，检索时前后文全是半句话。
def _cell_clean(v):
    v = (v or '').replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', v)
    v = re.sub(r'\s{2,}', ' ', v)
    return v.strip()

def _col_idx(ref):
    """单元格引用 'AB12' -> 列序号(0起)。用于把空单元格补回来、保证列不错位。"""
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return n - 1 if n else 0

def xlsx_text(p):
    """提取 xlsx：按行输出，单元格之间用制表符分隔。只用标准库(zip + ElementTree)。"""
    import xml.etree.ElementTree as ET
    def loc(tag):
        return tag.split('}')[-1]

    z = zipfile.ZipFile(p)
    names = z.namelist()

    # 1) 共享字符串池
    shared = []
    if 'xl/sharedStrings.xml' in names:
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root:
            if loc(si.tag) != 'si':
                continue
            shared.append(''.join(t.text or '' for t in si.iter() if loc(t.tag) == 't'))

    # 2) 工作表名单与顺序
    sheets = []
    if 'xl/workbook.xml' in names:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        for el in wb.iter():
            if loc(el.tag) == 'sheet':
                sheets.append(el.get('name') or '')

    cand = sorted(n for n in names
                  if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'))
    out = []
    for idx in range(len(sheets) or len(cand)):
        sname = sheets[idx] if idx < len(sheets) else ('Sheet%d' % (idx + 1))
        path = 'xl/worksheets/sheet%d.xml' % (idx + 1)
        if path not in names:
            if idx < len(cand):
                path = cand[idx]
            else:
                continue
        try:
            root = ET.fromstring(z.read(path))
        except Exception:
            continue
        lines = []
        for row in root.iter():
            if loc(row.tag) != 'row':
                continue
            cells = []
            for c in row:
                if loc(c.tag) != 'c':
                    continue
                col = _col_idx(c.get('r') or '')
                t = c.get('t')
                v = ''
                if t == 'inlineStr':
                    v = ''.join(x.text or '' for x in c.iter() if loc(x.tag) == 't')
                else:
                    for x in c:
                        if loc(x.tag) == 'v':
                            v = x.text or ''
                            break
                if t == 's' and v.isdigit() and int(v) < len(shared):
                    v = shared[int(v)]
                v = _cell_clean(v)
                if v:
                    cells.append((col, v))
            if not cells:
                continue
            arr = [''] * (max(col for col, _ in cells) + 1)
            for col, v in cells:
                arr[col] = v
            line = '\t'.join(arr).rstrip('\t')
            if line.strip():
                lines.append(line)
        if lines:
            out.append('【工作表：%s】' % sname)
            out.extend(lines)
    return '\n'.join(out)

def _xlrd_value(sh, r, c):
    """单元格转字符串：日期转成年月日，整数数字去掉多余的 .0（否则题号会变成 1.0）。"""
    t = sh.cell_type(r, c)
    v = sh.cell_value(r, c)
    if t == 3:  # XL_CELL_DATE
        try:
            tp = xlrd.xldate_as_tuple(v, sh.book.datemode)
            return '%04d-%02d-%02d' % (tp[0], tp[1], tp[2])
        except Exception:
            return str(v)
    if t == 2:  # XL_CELL_NUMBER
        try:
            f = float(v)
            return str(int(round(f))) if abs(f - round(f)) < 1e-9 else ('%g' % f)
        except Exception:
            return str(v)
    return str(v)

def xls_text(p):
    """提取老格式 xls（BIFF8 二进制）。用成熟解析器 xlrd，比手写记录解析可靠得多。"""
    if not HAVE_XLRD:
        return ''
    try:
        bk = xlrd.open_workbook(p)
    except Exception:
        return ''
    out = []
    for sh in bk.sheets():
        lines = []
        for i in range(sh.nrows):
            vals = [_cell_clean(_xlrd_value(sh, i, j)) for j in range(sh.ncols)]
            while vals and vals[-1] == '':
                vals.pop()
            if not any(vals):
                continue
            lines.append('\t'.join(vals))
        if lines:
            out.append('【工作表：%s】' % sh.name)
            out.extend(lines)
    return '\n'.join(out)

def convert(path):
    """返回 (文本, 方法说明)。pdf 逐页分流，doc/docx/xls/xlsx/txt 直接提取。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        if pdf_is_encrypted(path):
            return '', '加密PDF，无法提取（请先解除密码）'
        return convert_pdf(path)
    if ext == '.docx':
        if not is_zip_file(path):
            # 扩展名写的是 docx，实际是老格式 doc（常见于手工改名/另存为选错类型）
            return doc_text(path), 'Word(doc)提取（实际是老doc格式）'
        return docx_text(path), 'Word(docx)提取'
    if ext == '.doc':
        if is_zip_file(path):
            # 扩展名写的是 doc，实际是 docx
            return docx_text(path), 'Word(docx)提取（实际是docx）'
        return doc_text(path), 'Word(doc)提取'
    if ext == '.txt':
        return open(path, encoding='utf-8', errors='ignore').read(), '文本'
    if ext == '.xlsx':
        if not is_zip_file(path):
            # 后缀 xlsx 但其实是老 xls（手工改名常见）
            if HAVE_XLRD:
                return xls_text(path), 'Excel(xls)题库提取（实际是老xls）'
            return '', '不支持的类型（实际是老xls，缺解析库）'
        return xlsx_text(path), 'Excel(xlsx)题库提取'
    if ext == '.xls':
        if is_zip_file(path):
            return xlsx_text(path), 'Excel(xlsx)题库提取（实际是xlsx）'
        if HAVE_XLRD:
            return xls_text(path), 'Excel(xls)题库提取'
        return '', '不支持的类型（xls 解析库缺失）'
    return '', '不支持的类型'

def archive_name(fn):
    return os.path.splitext(fn)[0] + '.txt'

def all_archive_files():
    """列出所有归档文件。优先使用 v2 索引，无索引则回退基线文件扫描。
    返回 [(文件名, 完整路径)]。"""
    if DB_MANAGER:
        files, _ = DB_MANAGER.list_files(page=1, page_size=10000)
        return [(f['archive_name'], f['name']) for f in files]
    
    # 基线回退
    seen = set()
    out = []
    for d in ARCHIVE_DIRS:
        try:
            fs = sorted(os.listdir(d))
        except Exception:
            continue
        for f in fs:
            if f.endswith('.txt') and f not in seen:
                seen.add(f)
                out.append((f, os.path.join(d, f)))
    return out

def save_archive_v2(name, text, original_name, original_path, extract_method, page_count):
    """v2 归档：写入文本到 texts/ + 索引入库。返回 (success, message, dir)。"""
    # L762 的 save_archive_v2 在全局作用域调用 file_sha256，但它只在局部 try 块中导入
    # 所以需要在此处 import，或改用 index_db 模块的完整引用
    from index_db import file_sha256 as _sha256
    if not DB_MANAGER:
        return False, '索引管理器未初始化', ''
    
    # 计算 SHA256
    # 文本写入临时文件再算哈希（避免大文本在内存中重复）
    tmp_text = os.path.join(tempfile.mkdtemp(prefix='v2_'), name)
    try:
        with open(tmp_text, 'w', encoding='utf-8') as f:
            f.write(text)
        
        sha = _sha256(tmp_text)
        size = os.path.getsize(tmp_text)
        
        # 查重
        dup = DB_MANAGER.is_duplicate(sha)
        if dup['duplicate']:
            return False, '重复文件（%s）' % dup['existing_name'], ''
        
        # 写入 v2/texts/
        os.makedirs(V2_TEXTS, exist_ok=True)
        text_path = os.path.join(V2_TEXTS, name)
        shutil.copy2(tmp_text, text_path)
        
        # 原件副本
        if original_path:
            os.makedirs(V2_FILES, exist_ok=True)
            shutil.copy2(original_path, os.path.join(V2_FILES, os.path.basename(original_path)))
        
        # 索引入库
        success, msg = DB_MANAGER.add_file(original_name, name, text_path,
                                           os.path.join(V2_FILES, os.path.basename(original_path)) if original_path else None,
                                           sha, size, extract_method, page_count)
        
        return success, msg, V2_TEXTS
    except Exception as e:
        shutil.rmtree(os.path.dirname(tmp_text), ignore_errors=True)
        return False, str(e), ''

def save_archive(name, text, original_name='', original_path='', extract_method='文本', page_count=0):
    """把转换结果写进归档。优先 v2 结构，失败降级到 v1。
    返回 (实际写入的目录, 错误信息)；全部失败时目录为空串。"""
    # 尝试 v2
    ok, msg, v2_dir = save_archive_v2(name, text, original_name, original_path, extract_method, page_count)
    if ok:
        return v2_dir, ''
    
    # 降级基线
    errs = []
    tmp_dir = os.path.join(tempfile.gettempdir(), '检索归档')
    for i, d in enumerate(ARCHIVE_DIRS):
        try:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
                f.write(text)
            if d == tmp_dir and i > 0:
                print('[警告] 归档降级到临时目录: %s' % tmp_dir)
            return d, ''
        except Exception as e:
            errs.append('%s -> %s' % (d, str(e)[:60]))
    return '', '；'.join(errs)

# 形近字混淆表（来自 GitHub 项目 Macielyoung/Confused_Chinese，6153 对 + 实测补充）
def _load_confusable():
    try:
        with open(os.path.join(BASE, '形近字表.json'), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

FONT_CONFUSABLE = _load_confusable()

def chinese_bigram(text, n=2):
    """对中文文本进行 bigram 切分（零依赖）。
    提取中文字符序列，生成所有长度为 n 的连续子序列。
    用于 T1/T2/T3 中文检索、索引、条款感知匹配。"""
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    if len(chinese_chars) < n:
        return set(chinese_chars)
    return set(''.join(chinese_chars[i:i+n]) for i in range(len(chinese_chars) - n + 1))

def fuzzy_in(term, text):
    """容错匹配（应对 OCR 错字）：精确命中 > 形近字替换 > 去一字。"""
    if term in text:
        return True
    # 形近字替换：容首/中/尾字的识别错（如 孟→备、责→贡、替→蔡）
    if len(term) >= 2:
        for i, ch in enumerate(term):
            for conf in FONT_CONFUSABLE.get(ch, []):
                variant = term[:i] + conf + term[i + 1:]
                if variant in text:
                    return True
    # 去一字：容「文档少/多一个字」的情况（仅纯中文 3 字以上词，避免数字/英文无意义去字）
    if len(term) >= 3 and all('\u4e00' <= c <= '\u9fff' for c in term):
        for i in range(len(term)):
            sub = term[:i] + term[i + 1:]
            if len(sub) >= 2 and sub in text:
                return True
    return False

def strip_headers_footers(text, page_count):
    """剔除跨页重复的页眉页脚/页码。页数太少时不剔除，避免误删正文短句。"""
    if page_count < 5:
        return text
    from collections import Counter
    lines = text.split('\n')
    def norm(l):
        return re.sub(r'[\d\s]', '', l)
    cnt = Counter(norm(l) for l in lines if l.strip())
    out = []
    for l in lines:
        n = norm(l)
        if n and cnt[n] >= max(3, page_count * 0.6) and len(n) < 30:
            continue  # 页眉页脚，跳过
        out.append(l)
    return '\n'.join(out)

# ---------- HTTP 处理 ----------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype='application/json', disposition=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        if disposition:
            self.send_header('Content-Disposition', 'attachment; filename=%s' % disposition)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        path = unquote(u.path)
        if path == '/' or path == '/index.html':
            # 顶部显示所有实际存在的归档目录，降级后用户能一眼看到文件到底存哪了
            known = [d for d in ARCHIVE_DIRS if os.path.isdir(d)]
            html = INDEX_HTML.replace('__ARCHIVE__', '　|　'.join(known) or ARCHIVE)
            html = html.replace('__OCRENGINE__', ocr_engine_desc())
            self._send(200, html, 'text/html')
        elif path == '/files':
            # 优先走索引数据库（T2 分页 + T3 条款感知）
            if DB_MANAGER:
                try:
                    page = int(parse_qs(u.query).get('page', ['1'])[0])
                    files, total = DB_MANAGER.list_files(page=page, page_size=50)
                    self._send(200, json.dumps({'total': total, 'page': page, 'files': files}, ensure_ascii=False))
                    return
                except Exception:
                    pass
            # 降级：基线文件扫描
            info = [{'name': f, 'size': os.path.getsize(p), 'dir': os.path.dirname(p)}
                    for f, p in all_archive_files()]
            self._send(200, json.dumps({'total': len(info), 'page': 1, 'files': info}, ensure_ascii=False))
        
        elif path == '/backup':
            # T6 备份导出：打包所有归档文件为 zip
            try:
                import zipfile
                import io
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for d in (V2_TEXTS,) + tuple(ARCHIVE_DIRS):
                        if not os.path.isdir(d):
                            continue
                        for fn in os.listdir(d):
                            fp = os.path.join(d, fn)
                            if os.path.isfile(fp):
                                zf.write(fp, os.path.join(os.path.basename(d), fn))
                    # 打包 archive.db
                    for d in (V2_ARCHIVE,) + tuple(ARCHIVE_DIRS):
                        if d:
                            db_path = os.path.join(d, 'archive.db')
                            if os.path.exists(db_path):
                                zf.write(db_path, 'archive/backup.db')
                                break
                self._send(200, buf.getvalue(), 'application/zip', 'archive_backup_%s.zip' % datetime.now().strftime('%Y%m%d'))
            except Exception as e:
                self._send(500, json.dumps({'ok': False, 'err': str(e)}, ensure_ascii=False))
        elif path.startswith('/search'):
            q = parse_qs(u.query).get('q', [''])[0].strip()
            terms = q.split()
            if not terms:
                self._send(200, json.dumps({'fuzzy': False, 'result': []}, ensure_ascii=False))
                return
            
            # 优先走索引查询（T1 bigram + T2 排序分页 + T3 条款感知）
            if DB_MANAGER:
                try:
                    # 先尝试索引查询
                    page = int(parse_qs(u.query).get('page', ['1'])[0])
                    results, total, pg, ps = DB_MANAGER.search(' '.join(terms), page=page, page_size=20)
                    
                    # 格式化结果（T3 条款感知）
                    formatted = []
                    for r in results:
                        hit_item = {
                            'name': r['name'],
                            'clause_count': r.get('clause_count', 0),
                            'hits': []
                        }
                        for h in r.get('hits', [])[:20]:
                            hit = {'line_text': h.get('line_text', '')}
                            if 'clause' in h:
                                hit['clause'] = h['clause']
                            hit_item['hits'].append(hit)
                        formatted.append(hit_item)
                    
                    self._send(200, json.dumps({
                        'fuzzy': False,
                        'total': total,
                        'page': page,
                        'ps': ps,
                        'result': formatted
                    }, ensure_ascii=False))
                    return
                except Exception as e:
                    print(f'[搜索] DB_MANAGER.search 失败: {e}', flush=True)
                    import traceback
                    traceback.print_exc()
                    # 索引查询失败，降级基线
                    pass
            
            # 基线回退：大内存扫描 + bigram + 形近字容错
            filedata = []
            for f, p in all_archive_files():
                try:
                    lines = open(p, encoding='utf-8').read().split('\n')
                    filedata.append((f, lines))
                except Exception:
                    continue
            
            # 文件级 AND：每个查询词必须命中
            def hit_file(lines):
                full = '\n'.join(lines)
                return all(fuzzy_in(t, full) for t in terms)
            
            candidates = [fd for fd in filedata if hit_file(fd[1])]
            used_fuzzy = False
            if not candidates:
                # 降级精确匹配
                def exact_hit_file(lines):
                    full = '\n'.join(lines)
                    return all(t in full for t in terms)
                candidates = [fd for fd in filedata if exact_hit_file(fd[1])]
                if candidates:
                    used_fuzzy = False
            
            result = []
            for f, lines in candidates:
                hits = []
                full_text = '\n'.join(lines)
                for i, line in enumerate(lines):
                    if not line.strip():
                        continue
                    matched = [t for t in terms if fuzzy_in(t, line)]
                    if matched:
                        win = []
                        for k in (i - 2, i - 1, i, i + 1, i + 2):
                            if 0 <= k < len(lines) and lines[k].strip():
                                win.append((k, lines[k]))
                        ctx = [snip(t, matched) for _, t in win]
                        ci = 0
                        for pos, (k, _) in enumerate(win):
                            if k == i:
                                ci = pos
                        hits.append({'n': i + 1, 'line': snip(line, matched),
                                     'kw': matched, 'ctx': ctx, 'ci': ci})
                if hits:
                    result.append({'name': f, 'hits': hits[:300], 'total': len(hits)})
            self._send(200, json.dumps({'fuzzy': used_fuzzy, 'result': result}, ensure_ascii=False))
        elif path.startswith('/file/'):
            fn = os.path.basename(unquote(path[len('/file/'):]))
            fp = ''
            for _, p in all_archive_files():
                if os.path.basename(p) == fn:
                    fp = p
                    break
            if fp and os.path.exists(fp):
                self._send(200, open(fp, encoding='utf-8').read(), 'text/plain')
            else:
                self._send(404, 'not found', 'text/plain')
        else:
            self._send(404, 'not found', 'text/plain')

    def do_POST(self):
        u = urlparse(self.path)
        
        # T7: HTTP 线程上限
        if not _HTTP_SEM.acquire(blocking=False):
            self._send(503, json.dumps({'ok': False, 'err': '服务繁忙，线程上限%d，请稍后重试' % MAX_HTTP_THREADS}))
            return
        
        try:
            if u.path == '/upload':
                # T7: Content-Length 前置校验（200MB 限长）
                max_upload_size = 200 * 1024 * 1024  # 200MB
                length = int(self.headers.get('Content-Length', 0))
                if length > max_upload_size:
                    # T7: Content-Length 超限在读体前即拒绝，直接返回 413 并关闭连接
                    self._send(413, json.dumps({
                        'ok': False,
                        'err': '文件过大（%d bytes，上限 %d bytes / 200MB）' % (length, max_upload_size)
                    }, ensure_ascii=False))
                    self.wfile.close()
                    return
                
                q = parse_qs(u.query)
                fn = unquote(q.get('name', ['file'])[0])
                
                # 文件名消毒（T7 路径穿越防护）
                fn = os.path.basename(fn)
                if not fn or fn.startswith('.'):
                    self._send(400, json.dumps({'ok': False, 'err': '非法文件名'}))
                    return
                
                # T7: 流式写盘——逐块读取,避免大文件全量驻留内存
                tmp = os.path.join(tempfile.mkdtemp(prefix='up_'), os.path.basename(fn))
                BUF = 65536  # 64KB 缓冲
                sha = hashlib.sha256()
                with open(tmp, 'wb') as f:
                    while length > 0:
                        chunk = self.rfile.read(min(length, BUF))
                        if not chunk:
                            break
                        f.write(chunk)
                        sha.update(chunk)
                        length -= len(chunk)
                try:
                    text, method = convert(tmp)
                except Exception as e:
                    self._send(500, json.dumps({'name': fn, 'ok': False, 'err': str(e)}, ensure_ascii=False))
                    shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
                    return
                if not text:
                    self._send(200, json.dumps({'name': fn, 'ok': False, 'err': method}, ensure_ascii=False))
                    shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
                    return
                an = archive_name(fn)
                # v2 归档：保留原件副本 + SHA256 查重（先调用再删tmp，因为save_archive_v2需要original_path）
                ok, werr, real_dir = save_archive_v2(an, text, fn, tmp, method, 0)
                shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
                if not ok:
                    # 查重失败或存盘失败
                    self._send(200, json.dumps(
                        {'name': fn, 'ok': False, 'err': werr},
                        ensure_ascii=False))
                    return
                self._send(200, json.dumps({
                    'name': fn, 'ok': True, 'method': method,
                    'chars': len(text), 'archived': an,
                    'dir': real_dir, 'duplicate': False
                }, ensure_ascii=False))
                
            elif u.path == '/archive/delete':
                # 删除归档文件 API（POST）
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(length)
                    data = json.loads(body.decode('utf-8'))
                    fn = data.get('name', '')
                    if not fn:
                        self._send(400, json.dumps({'ok': False, 'err': '缺少文件名'}))
                        return
                    # 优先走索引删除
                    if DB_MANAGER:
                        ok, msg = DB_MANAGER.delete_file(fn)
                        self._send(200, json.dumps({'ok': ok, 'name': fn, 'msg': msg}))
                        return
                    # 基线回退
                    fp = ''
                    for _, p in all_archive_files():
                        if os.path.basename(p) == fn:
                            fp = p
                            break
                    if not fp or not os.path.exists(fp):
                        self._send(404, json.dumps({'ok': False, 'err': '文件不存在'}))
                        return
                    os.remove(fp)
                    self._send(200, json.dumps({'ok': True, 'name': fn}))
                except Exception as e:
                    self._send(500, json.dumps({'ok': False, 'err': str(e)}))
            else:
                self._send(404, 'not found')
        finally:
            _HTTP_SEM.release()

    def log_message(self, *a):
        pass

# ---------- 前端界面 ----------
INDEX_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>资料归档检索系统</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--text:#1a1a1a;--sub:#666;--line:#e5e7eb;
--accent:#1f6feb;--accent-soft:#e8f0fe;--hit:#fff3cd;--ok:#1a7f37;--err:#c62828;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,"Microsoft YaHei","PingFang SC",sans-serif;background:var(--bg);color:var(--text);padding:24px;}
.wrap{max-width:960px;margin:0 auto;}
h1{font-size:20px;margin-bottom:4px;}
.sub{color:var(--sub);font-size:13px;margin-bottom:16px;}
.tabs{display:flex;gap:8px;margin-bottom:16px;}
.tabs button{padding:9px 20px;border:1px solid var(--line);background:var(--card);border-radius:8px;
  cursor:pointer;font-size:14px;color:var(--text);}
.tabs button.on{background:var(--accent);color:#fff;border-color:var(--accent);}
.panel{display:none;}
.panel.on{display:block;}
.drop{border:2px dashed var(--line);border-radius:12px;padding:40px;text-align:center;
  background:var(--card);cursor:pointer;transition:.15s;}
.drop.drag{border-color:var(--accent);background:var(--accent-soft);}
.drop .big{font-size:15px;font-weight:600;}
.drop .hint{color:var(--sub);font-size:13px;margin-top:6px;}
#fileList{margin-top:12px;}
#fileList .item{display:flex;justify-content:space-between;align-items:center;background:var(--card);
  border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:14px;}
#fileList .item .st{color:var(--sub);font-size:12px;margin-left:10px;white-space:nowrap;}
#fileList .item .ok{color:var(--ok);}
#fileList .item .err{color:var(--err);}
.searchbar input{width:100%;padding:14px 18px;font-size:16px;border:1px solid var(--line);
  border-radius:10px;outline:none;}
.searchbar input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);}
.stats{color:var(--sub);font-size:13px;margin:8px 0 16px;}
.file-block{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:14px;overflow:hidden;}
.file-head{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;
  cursor:pointer;border-bottom:1px solid var(--line);}
.file-head:hover{background:#fafbfc;}
.file-name{font-weight:600;font-size:14px;}
.file-count{color:var(--sub);font-size:12px;white-space:nowrap;margin-left:12px;}
.hits{padding:8px 16px;}
.hit{padding:10px 0;border-bottom:1px dashed var(--line);font-size:14px;line-height:1.7;}
.hit:last-child{border-bottom:none;}
.hit .ln{color:#9aa0a6;font-size:12px;margin-right:8px;user-select:none;}
.hit mark{background:var(--hit);color:inherit;padding:0 2px;border-radius:2px;}
.empty{text-align:center;color:var(--sub);padding:50px 0;}
.collapsed .hits{display:none;}
.row{display:flex;justify-content:space-between;align-items:center;background:var(--card);
  border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:14px;}
.row .sz{color:var(--sub);font-size:12px;}
</style>
</head>
<body>
<div class="wrap">
<h1>资料归档检索系统</h1>
<div class="sub">投喂 Word/PDF → 自动转换归档 → 检索（全程离线，本机处理）</div>
<div class="sub" style="color:#1f6feb;font-weight:600">归档目录：__ARCHIVE__　← 转好的文字都存在这里</div>
<div class="sub">图文识别引擎：__OCRENGINE__</div>

<div class="tabs">
  <button id="tabUpload" class="on" onclick="switchTab('upload')">投喂归档</button>
  <button id="tabSearch" onclick="switchTab('search')">检索</button>
  <button id="tabFiles" onclick="switchTab('files')">已归档 (0)</button>
  <button id="tabManage" onclick="switchTab('manage')">管理</button>
</div>

<div id="panel-upload" class="panel on">
  <div class="drop" id="drop" onclick="document.getElementById('f').click()">
    <div class="big">点击选择文件，或拖拽文件到这里</div>
    <div class="hint">支持 .pdf .doc .docx .xlsx .xls .txt，可多选。文字版PDF秒转，扫描件自动OCR，Excel成行解析。</div>
  </div>
  <input type="file" id="f" multiple accept=".pdf,.doc,.docx,.xlsx,.xls,.txt" style="display:none">
  <div class="sub" style="margin-top:14px;line-height:1.8">
    注意事项：<br>
    ① 支持 .pdf .doc .docx .xlsx .xls .txt，可多选；<br>
    ② 扫描件（纸质扫描的 PDF）识别慢，一页约几秒，别急；<br>
    ② 加密的 PDF 会提示「加密PDF无法提取」，需先解除密码再投；<br>
    ③ 一次别拖太多，几十个文件可以分批来；<br>
    ④ 处理完的文件自动存到上面的「归档目录」，可随时打开查看。
  </div>
  <div id="fileList"></div>
</div>

<div id="panel-search" class="panel">
  <div class="searchbar"><input id="q" placeholder="输入关键词检索（空格分隔多关键词）"></div>
  <div class="stats" id="stats"></div>
  <div id="pagination" style="display:none;justify-content:center;align-items:center;gap:8px;margin-bottom:16px;">
    <button id="prevPage" onclick="goPage(currentPage-1)" style="padding:6px 14px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;">上一页</button>
    <span id="pageInfo" style="color:var(--sub);font-size:13px;min-width:100px;text-align:center;">第 1 页</span>
    <button id="nextPage" onclick="goPage(currentPage+1)" style="padding:6px 14px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;">下一页</button>
  </div>
  <div id="results"><div class="empty">等待输入关键词…</div></div>
</div>

<div id="panel-files" class="panel">
  <div id="archiveList"><div class="empty">加载中…</div></div>
</div>

<div id="panel-manage" class="panel">
  <div style="display:flex;gap:8px;margin-bottom:12px;">
    <input id="manageSearch" placeholder="搜索文件…" style="flex:1;padding:10px 14px;font-size:14px;border:1px solid var(--line);border-radius:8px;">
    <button onclick="loadManageFiles()" style="padding:10px 20px;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer;">刷新</button>
    <button onclick="exportBackup()" style="padding:10px 20px;background:var(--ok);color:#fff;border:none;border-radius:8px;cursor:pointer;">备份导出</button>
  </div>
  <div id="manageList"><div class="empty">加载中…</div></div>
</div>
</div>

<script>
function switchTab(t){
  ['upload','search','files'].forEach(function(x){
    document.getElementById('panel-'+x).classList.toggle('on', x===t);
    document.getElementById('tab'+x.charAt(0).toUpperCase()+x.slice(1)).classList.toggle('on', x===t);
  });
  if(t==='files')loadFiles();
  if(t==='manage')loadManageFiles();
}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function fmt(n){return n>1024*1024?(n/1024/1024).toFixed(1)+' MB':(n>1024?(n/1024).toFixed(0)+' KB':n+' B');}

var drop=document.getElementById('drop');
var input=document.getElementById('f');
input.addEventListener('change',function(){handleFiles(input.files);input.value='';});
drop.addEventListener('dragover',function(e){e.preventDefault();drop.classList.add('drag');});
drop.addEventListener('dragleave',function(){drop.classList.remove('drag');});
drop.addEventListener('drop',function(e){e.preventDefault();drop.classList.remove('drag');handleFiles(e.dataTransfer.files);});

async function handleFiles(files){
  var list=document.getElementById('fileList');
  for(var i=0;i<files.length;i++){
    var f=files[i];
    var div=document.createElement('div');
    div.className='item';div.id='it_'+i;
    div.innerHTML='<span>'+esc(f.name)+'</span><span class="st">转换中…</span>';
    list.appendChild(div);
    try{
      var r=await fetch('/upload?name='+encodeURIComponent(f.name),{method:'POST',body:f});
      var j=await r.json();
      var st=document.querySelector('#it_'+i+' .st');
      if(j.ok){st.textContent='✓ '+j.method+'（'+fmt(j.chars*3)+'）';st.className='st ok';}
      else{st.textContent='✗ '+j.err;st.className='st err';}
    }catch(e){
      var st2=document.querySelector('#it_'+i+' .st');
      st2.textContent='✗ '+e;st2.className='st err';
    }
    loadFiles();
  }
}

async function loadFiles(){
  try{
    var r=await fetch('/files');var data=await r.json();
    var arr=data.files||[];
    document.getElementById('tabFiles').textContent='已归档 ('+data.total+')';
    var list=document.getElementById('archiveList');
    if(!arr.length){list.innerHTML='<div class="empty">还没有归档文件，先去「投喂归档」添加</div>';return;}
    var html='';
    for(var i=0;i<arr.length;i++){
      var extra = arr[i].page_count ? ' '+arr[i].page_count+'页' : '';
      extra += arr[i].clause_count ? ' '+arr[i].clause_count+'条' : '';
      html+='<div class="row"><span>'+esc(arr[i].name)+extra+'</span><span class="sz">'+fmt(arr[i].file_size||0)+'</span></div>';
    }
    list.innerHTML=html;
  }catch(e){}
}

function exportBackup(){
  window.open('/backup', '_blank');
}

async function loadManageFiles(){
  try{
    var r=await fetch('/files');var data=await r.json();
    var arr=data.files||[];
    var list=document.getElementById('manageList');
    if(!arr.length){list.innerHTML='<div class="empty">还没有归档文件</div>';return;}
    var html='';
    for(var i=0;i<arr.length;i++){
      html+='<div class="row"><span>'+esc(arr[i].name)+'</span><span style="display:flex;gap:8px;align-items:center;">'
        +'<span class="sz">'+fmt(arr[i].file_size||0)+'</span>'
        +'<button onclick="deleteFile(\''+esc(arr[i].name)+'\')" style="padding:4px 10px;background:var(--err);color:#fff;border:none;border-radius:4px;cursor:pointer;">删除</button>'
        +'</span></div>';
    }
    list.innerHTML=html;
  }catch(e){}
}

async function deleteFile(name){
  if(!confirm('确定删除 '+name+'？'))return;
  try{
    var r=await fetch('/archive/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})});
    var j=await r.json();
    if(j.ok){alert('已删除');loadManageFiles();loadFiles();}
    else{alert('删除失败：'+j.err);}
  }catch(e){alert('删除失败：'+e);}
}

var currentPage = 1;

function highlight(line,terms){
  var out=esc(line);
  for(var i=0;i<terms.length;i++){var t=terms[i];
    if(!t)continue;out=out.split(esc(t)).join('<mark>'+esc(t)+'</mark>');}
  return out;
}
async function search(page){
  page = page || 1;
  currentPage = page;
  var q=document.getElementById('q').value.trim();
  var res=document.getElementById('results'),stats=document.getElementById('stats');
  if(!q){res.innerHTML='<div class="empty">等待输入关键词…</div>';stats.textContent='';document.getElementById('pagination').style.display='none';return;}
  var r=await fetch('/search?q='+encodeURIComponent(q)+'&page='+encodeURIComponent(page));
  var data=await r.json();
  var arr=data.result||[];
  var terms=q.split(/\\s+/).filter(Boolean);
  var tf=0,th=0,html='';
  for(var i=0;i<arr.length;i++){
    var f=arr[i];tf++;th+=f.hits.length;
    html+='<div class="file-block"><div class="file-head" onclick="this.parentNode.classList.toggle(&quot;collapsed&quot;)">'
      +'<span class="file-name">'+esc(f.name)+'</span>'
      +'<span class="file-count">命中 '+f.hits.length+' 处'+(f.hits.length>300?'（显示前300）':'')+'</span>'
      +'</div><div class="hits">';
    for(var m=0;m<f.hits.length;m++){
      var h=f.hits[m];
      var clauseTag = h.clause ? '<span style="color:#1f6feb;font-size:12px;margin-right:6px;">['+esc(h.clause)+']</span>' : '';
      html+='<div class="hit"><span class="ln">'+clauseTag+'</span><div>'+highlight(h.line_text,terms)+'</div></div>';
    }
    html+='</div></div>';
  }
  var totalPg = data.page || 1;
  var totalPs = data.ps || 20;
  stats.textContent='共 '+tf+' 个文件命中 '+th+' 处'+(data.fuzzy?'（未精确命中，已容错搜索，可能有 OCR 误差）':'')+(data.total?' （共 '+data.total+' 条结果，第 '+totalPg+'/'+Math.ceil(data.total/totalPs)+' 页）':'');
  res.innerHTML=html||'<div class="empty">没有找到匹配的内容</div>';
  // 更新分页控件
  var pag=document.getElementById('pagination');
  if(data.total && data.total > totalPs){
    pag.style.display='flex';
    document.getElementById('prevPage').disabled = (page<=1);
    document.getElementById('nextPage').disabled = (page*totalPs >= data.total);
    document.getElementById('pageInfo').textContent='第 '+page+'/'+Math.ceil(data.total/totalPs)+' 页';
  } else {
    pag.style.display='none';
  }
}
function goPage(p){
  if(p<1)return;
  var q=document.getElementById('q').value.trim();
  if(!q)return;
  search(p);
}
document.getElementById('q').addEventListener('input',function(){clearTimeout(this._t);this._t=setTimeout(search,200);});

loadFiles();

function loadManageFiles(){
  fetch('/files').then(function(r){return r.json();}).then(function(files){
    var list=document.getElementById('manageList');
    if(!files.length){list.innerHTML='<div class="empty">没有归档文件</div>';return;}
    var html='';
    for(var i=0;i<files.length;i++){
      html+='<div class="row"><span>'+esc(files[i].name)+' <span class="sz">'+fmt(files[i].size)+'</span></span>'
        +'<button onclick="deleteFile(\''+encodeURIComponent(files[i].name)+'\')" style="padding:6px 14px;background:var(--err);color:#fff;border:none;border-radius:6px;cursor:pointer;">删除</button>'
        +'</div>';
    }
    list.innerHTML=html;
  });
}

async function deleteFile(name){
  if(!confirm('确定要删除 "'+decodeURIComponent(name)+'" 吗？'))return;
  try{
    var r=await fetch('/archive/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:decodeURIComponent(name)})});
    var j=await r.json();
    if(j.ok){alert('已删除');loadManageFiles();}
    else{alert('删除失败: '+j.err);}
  }catch(e){alert('请求失败: '+e);}
}

document.getElementById('manageSearch').addEventListener('input',function(){
  var q=this.value.trim().toLowerCase();
  var rows=document.getElementById('manageList').querySelectorAll('.row');
  for(var i=0;i<rows.length;i++){
    var name=rows[i].querySelector('span').textContent.toLowerCase();
    rows[i].style.display=name.indexOf(q)!==-1?'':'none';
  }
});
</script>
</body>
</html>'''

def main():
    print('=' * 46)
    print('  资料归档检索系统')
    print('  归档目录:', ARCHIVE)
    print('  识别引擎:', ocr_engine_desc())
    print('=' * 46)
    # 初始化索引管理器（T1/T2/T3/T4 核心）
    _init_index_manager()
    class ReuseServer(ThreadingTCPServer):
        allow_reuse_address = True   # 端口复用，避免重启时 TIME_WAIT 导致 bind 失败
        daemon_threads = True        # 主线程退出时子线程自动结束
    httpd = None
    port = PORT
    for p in range(PORT, PORT + 10):   # 端口被占时自动顺延
        try:
            httpd = ReuseServer(('127.0.0.1', p), Handler)
            port = p
            break
        except OSError:
            continue
    if httpd is None:
        print('错误：端口 %d~%d 都被占用，请关闭占用程序后重试' % (PORT, PORT + 9))
        return
    print('  服务地址: http://127.0.0.1:%d' % port)
    print('  浏览器将自动打开，按 Ctrl+C 停止')
    print('=' * 46)
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:%d' % port)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')

if __name__ == '__main__':
    main()
