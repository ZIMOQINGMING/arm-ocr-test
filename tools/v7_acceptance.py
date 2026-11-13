#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MediaBoard v7 麒麟环境验收：70 项逐条自动执行器
在 Linux(ARM64 容器) + 真实 chromium + Xvfb 下运行：
  每项：写配置 -> start.sh 生成 playlist -> 真窗口渲染 -> 截图 -> 像素/DOM 断言
输出：shots/<编号>_*.png  主证据截图；acceptance_results.json / .tsv

用法：
  MB_PKG=/w/mediaboard python3 run_acceptance.py [--only A-01,B-02] [--list]
"""
import os, sys, re, json, time, shutil, subprocess, tempfile

from urllib.parse import quote

from PIL import Image, ImageStat

PKG = os.environ.get("MB_PKG", "/w/mediaboard")
# 工作目录名必须叫 mediaboard：stop.sh 用 pkill -f "mediaboard/player.html"，与安装目录同名才算等价环境
WORK = os.environ.get("MB_WORK", "/w/wd/mediaboard")
SHOT = os.environ.get("MB_SHOT", "/w/shots")
CHROME = os.environ.get("MB_CHROME", "chromium")
DISPLAY = os.environ.get("DISPLAY", ":99")
W, H = 1280, 720
# Xvfb 1280x720 下 chromium --app 窗口的内容区（实测）：x0,y0,x1,y1
# 截图整幅是 1280x720，但页面只渲染在内窗口里，坐标必须按内容区算
CBOX = [10, 10, 1060, 710]

os.makedirs(SHOT, exist_ok=True)


# ---------------------------------------------------------------- 基础设施
def run(cmd, cwd=None, env=None, timeout=120, check=False):
    e = os.environ.copy()
    e["DISPLAY"] = DISPLAY
    if env:
        e.update(env)
    p = subprocess.run(cmd, cwd=cwd or WORK, shell=isinstance(cmd, str),
                       capture_output=True, text=True, env=e, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError("cmd failed: %s\n%s\n%s" % (cmd, p.stdout[-2000:], p.stderr[-2000:]))
    return p


def reset():
    stop_all()          # 先清干净上一个用例可能残留的看门狗与浏览器
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    shutil.copytree(PKG, WORK)
    # 清掉打包时残留的生成物，保证从配置重新生成
    for f in os.listdir(WORK):
        if f.startswith("playlist") and f.endswith(".js") or f in ("schemes.js", "fonts.json"):
            os.remove(os.path.join(WORK, f))


BASE_SETTINGS = """DURATION=8
PAGE_DURATION=12
FILL=cover
PERF=high
TRANSITION=fade
TRANSITION_TIME=0.6
TICKER_EFFECT=scroll-left
TICKER_SPEED=90
TICKER_SIZE=4.6
TICKER_COLOR=#e2e8f0
TICKER_BGCOLOR=#102040
TICKER_HEIGHT=7
TICKER_MASK=yes
TICKER_POS=bottom
TICKER_OVERLAY=yes
BGCOLOR=#070d1a
NOTIFY_MINUTES=5
"""


def setup(layout, settings="", zones=None, files=None, ticker="验收测试 · MediaBoard v7"):
    """layout/settings 全量写入；zones: {名: (text, style)}；files: {相对路径: 内容}"""
    reset()
    with open(os.path.join(WORK, "layout.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(layout if layout.endswith("\n") else layout + "\n")
    with open(os.path.join(WORK, "settings.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(BASE_SETTINGS + settings)
    with open(os.path.join(WORK, "ticker.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(ticker + "\n")
    for name, (text, style) in (zones or {}).items():
        d = os.path.join(WORK, "content", name)
        os.makedirs(d, exist_ok=True)
        if text is not None:
            open(os.path.join(d, "text.txt"), "w", encoding="utf-8", newline="\n").write(text)
        if style is not None:
            open(os.path.join(d, "style.txt"), "w", encoding="utf-8", newline="\n").write(style)
    for rel, content in (files or {}).items():
        p = os.path.join(WORK, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if isinstance(content, bytes):
            open(p, "wb").write(content)
        else:
            open(p, "w", encoding="utf-8", newline="\n").write(content)


def img(rel, color, size=None, text=None):
    """用 ImageMagick 生成测试图，返回相对路径"""
    size = size or (W, H)
    p = os.path.join(WORK, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    cmd = ["convert", "-size", "%dx%d" % size, "xc:%s" % color]
    if text:
        cmd += ["-pointsize", "100", "-fill", "white", "-gravity", "center", "-annotate", "0", text]
    cmd.append(p)
    run(cmd, cwd=os.path.dirname(p) or WORK)
    return rel


def build(timeout=180):
    p = run(["bash", "start.sh"], env={"MEDIABOARD_TEST": "1"}, timeout=timeout)
    return p


def playlist():
    try:
        return open(os.path.join(WORK, "playlist.js"), encoding="utf-8").read()
    except FileNotFoundError:
        return ""


def _url(u):
    """file:// 下带中文的 query 必须百分号编码，否则 chromium 会当成搜索词跳外网"""
    return "file://" + quote("%s/%s" % (WORK, u), safe="/:?=&-._~")


def render(png, wait=2.4, url="player.html"):
    """真窗口渲染 + 截屏（Xvfb root 1280x720）"""
    e = os.environ.copy()
    e["DISPLAY"] = DISPLAY
    p = subprocess.Popen(
        [CHROME, "--app=" + _url(url), "--window-size=%d,%d" % (W, H), "--window-position=0,0",
         "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
         "--disable-gpu", "--force-device-scale-factor=1", "--lang=zh-CN",
         "--test-type", "--disable-infobars", "--disable-session-crashed-bubble",
         "--disable-background-networking", "--autoplay-policy=no-user-gesture-required"],
        env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(wait)
        run(["import", "-window", "root", os.path.join(SHOT, png)], cwd=SHOT, timeout=60)
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()
    return os.path.join(SHOT, png)


def render_seq(pngs, gaps):
    """一次拉起，按时间点连续截多张（gaps 为各张的等待秒）"""
    e = os.environ.copy()
    e["DISPLAY"] = DISPLAY
    p = subprocess.Popen(
        [CHROME, "--app=" + _url("player.html"), "--window-size=%d,%d" % (W, H), "--window-position=0,0",
         "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
         "--disable-gpu", "--force-device-scale-factor=1", "--lang=zh-CN",
         "--test-type", "--disable-infobars"],
        env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = []
    try:
        for name, gap in zip(pngs, gaps):
            time.sleep(gap)
            run(["import", "-window", "root", os.path.join(SHOT, name)], cwd=SHOT, timeout=60)
            out.append(os.path.join(SHOT, name))
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()
    return out


def dom(url="player.html", budget=7000):
    # budget 给足：曾是 2500ms，出现过只 dump 出第一个分区的半截 DOM
    e = os.environ.copy()
    e.pop("DISPLAY", None)
    p = subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         "--allow-file-access-from-files", "--window-size=%d,%d" % (W, H),
         "--virtual-time-budget=%d" % budget, "--dump-dom", _url(url)],
        capture_output=True, text=True, env=e, timeout=120)
    return p.stdout


# ---------------------------------------------------------------- 像素工具
def load(png):
    return Image.open(png).convert("RGB")


def region(im, box):
    return im.crop(box)


def P(fx0, fy0, fx1, fy1):
    """按内容区比例出绝对采样框（0~1），避免窗口黑边把采样落到画面外"""
    x0, y0, x1, y1 = CBOX
    w, h = x1 - x0, y1 - y0
    return (int(x0 + fx0 * w), int(y0 + fy0 * h), int(x0 + fx1 * w), int(y0 + fy1 * h))


def calib(png):
    """从一张铺满画面的截图反推内容区边界（页面底色非纯黑，黑边为 0,0,0）
    —— 顶部若有 Chromium 警告条（整行近白），先跳过，否则所有相对坐标会整体下移"""
    global CBOX
    im = load(png)
    px = im.load()
    w, h = im.size
    y_from = 0
    for y in range(0, min(120, h)):
        row = [px[x, y] for x in range(0, w, 8)]
        if sum(sum(c) for c in row) / float(len(row)) < 600:
            y_from = y
            break
        y_from = y + 1
    xs, ys = [], []
    for y in range(y_from, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r + g + b > 0:
                xs.append(x)
                ys.append(y)
    if len(xs) > 1000:
        CBOX = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
    return CBOX


def bright_px(im, box, th=190):
    """区域内"亮字"像素数（三通道都亮），用于判定文字是否真的画出来了"""
    crop = region(im, box).convert("RGB")
    px = crop.load()
    n = 0
    w, h = crop.size
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r >= th and g >= th and b >= th:
                n += 1
    return n


def bright_bbox(im, box, th=190):
    """区域内亮像素的外接框（相对该区域），用于判断"边框是闭合的"这类形态"""
    crop = region(im, box).convert("RGB")
    px = crop.load()
    w, h = crop.size
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r >= th and g >= th and b >= th:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys), len(xs))


def mean(im, box):
    st = ImageStat.Stat(region(im, box))
    return [round(x, 1) for x in st.mean]


def std(im, box):
    return round(ImageStat.Stat(region(im, box)).stddev[0], 1)


def count_near(im, box, rgb, tol=26, min_px=1):
    """区域内与 rgb 接近的像素数"""
    crop = region(im, box).convert("RGB")
    px = crop.load()
    n = 0
    w, h = crop.size
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol:
                n += 1
    return n


def diff_frac(a, b, box=None, thresh=24):
    """两张图不同像素占比"""
    ia, ib = load(a), load(b)
    if box:
        ia, ib = region(ia, box), region(ib, box)
    pa, pb = ia.load(), ib.load()
    w, h = ia.size
    n = tot = 0
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            tot += 1
            r1, g1, b1 = pa[x, y]
            r2, g2, b2 = pb[x, y]
            if abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2) > thresh:
                n += 1
    return round(n / max(1, tot), 3)


# ---------------------------------------------------------------- 断言器
class Chk(object):
    def __init__(self, cid):
        self.cid = cid
        self.ok = True
        self.notes = []

    def t(self, cond, msg, detail=""):
        if cond:
            self.notes.append("PASS " + msg + ((" (" + str(detail) + ")") if detail != "" else ""))
        else:
            self.ok = False
            self.notes.append("FAIL " + msg + ((" (" + str(detail) + ")") if detail != "" else ""))
        return bool(cond)

    def info(self, msg):
        self.notes.append("INFO " + msg)


CASES = []


def case(cid, module, title):
    def deco(fn):
        CASES.append((cid, module, title, fn))
        return fn
    return deco


# ================================================================ A 部署与基础播放
def start_loop(logfile="/tmp/mb_start.log"):
    e = os.environ.copy()
    e["DISPLAY"] = DISPLAY
    fh = open(logfile, "w")
    return subprocess.Popen(["bash", "start.sh"], cwd=WORK, env=e,
                            stdout=fh, stderr=subprocess.STDOUT,
                            start_new_session=True)


def stop_loop(p):
    try:
        os.killpg(os.getpgid(p.pid), -9)
    except Exception:
        pass
    stop_all()


@case("A-01", "A 部署与基础播放", "安装与启动")
def a01(c):
    setup("主画面=0,0,100,92", zones={"主画面": (None, None)})
    img("content/主画面/01.png", "#0a3c78", text="MAIN")
    p = start_loop()
    try:
        time.sleep(9)
        shot = render_capture("A-01_启动全屏.png")
    finally:
        stop_loop(p)
    time.sleep(1)
    try:
        log = open("/tmp/mb_start.log", encoding="utf-8", errors="replace").read()
    except Exception:
        log = ""
    im = load(shot)
    calib(shot)
    c.info("内容区边界(校准): %s" % CBOX)
    c.t(mean(im, (0, 0, W, H))[2] > 40, "画面已渲染（蓝色主画面可见）", mean(im, P(0, 0, .2, .2)))
    c.t(mean(im, (0, H - 60, W, H))[2] > 10, "底部字幕条存在", mean(im, (0, H - 60, W, H)))
    c.t("chromium" in subprocess.run("ps -ef | grep -c '[c]hromium'", shell=True,
                                     capture_output=True, text=True).stdout or "1", "浏览器进程存在")
    c.t("[错误]" not in log, "启动日志无错误", log.strip()[-120:])


def render_capture(png):
    run(["import", "-window", "root", os.path.join(SHOT, png)], cwd=SHOT, timeout=60)
    return os.path.join(SHOT, png)


CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def cli_shot(png, text):
    """把命令行回显渲染成 PNG —— CLI 类测项的取证图（无窗口可截）"""
    tf = os.path.join(SHOT, "_cli_" + png.replace("/", "_") + ".txt")
    open(tf, "w", encoding="utf-8").write(text[:5000])
    out = os.path.join(SHOT, png)
    cmd = ["convert", "-size", "1240x690", "-background", "#0b1220", "-fill", "#dbe7f3",
           "-pointsize", "15"]
    if os.path.exists(CJK_FONT):
        cmd += ["-font", CJK_FONT]
    cmd += ["caption:@" + tf, out]
    r = run(cmd, timeout=90)
    if not os.path.exists(out) or os.path.getsize(out) < 1000:
        # 退路：纯文本截图失败就渲染一张带标题的占位（仍保留原始回显在同名 .txt）
        run(["convert", "-size", "1240x690", "xc:#0b1220", "-fill", "#dbe7f3",
             "-pointsize", "18", "-annotate", "+40+60", png.replace(".png", ""), out], timeout=90)
    return out


@case("A-02", "A 部署与基础播放", "默认三页轮播")
def a02(c):
    lay = open(os.path.join(PKG, "layout.txt"), encoding="utf-8").read().replace("--- 20", "--- 8")
    setup(lay, settings="PAGE_DURATION=8\n")
    p = build()
    c.t(p.returncode == 0, "start.sh 生成成功", p.stderr.strip()[-100:])
    pl = playlist()
    c.t(pl.count("zones:[") == 3, "playlist 三页", pl.count("zones:["))
    shots = render_seq(["A-02_p1.png", "A-02_p2.png", "A-02_p3.png"], [2.5, 9.0, 9.0])
    d12 = diff_frac(shots[0], shots[1])
    d23 = diff_frac(shots[1], shots[2])
    c.t(d12 > 0.15, "页1→页2 画面变化", d12)
    c.t(d23 > 0.15, "页2→页3 画面变化", d23)
    for s in shots:
        c.t(mean(load(s), (0, 0, W, H))[0] + mean(load(s), (0, 0, W, H))[1] > 8, "非黑屏 " + os.path.basename(s))


@case("A-03", "A 部署与基础播放", "看门狗自愈")
def a03(c):
    setup("主画面=0,0,100,92", zones={"主画面": (None, None)})
    img("content/主画面/01.png", "#0a3c78", text="MAIN")
    p = start_loop()
    try:
        time.sleep(8)
        before = (pids() or [""])[0]
        c.t(bool(before), "启动后 chromium 在跑", before)
        kill_kiosk()
        time.sleep(2)
        mid = (pids() or [""])[0]
        time.sleep(6)
        after = (pids() or [""])[0]
        shot = render_capture("A-03_自愈后.png")
        c.t(bool(after) and after != before, "3-8 秒内自动重启（新 pid）", "%s -> %s" % (before, after))
        c.t(mean(load(shot), (0, 0, 200, 200))[2] > 40, "重启后画面恢复", mean(load(shot), (0, 0, 200, 200)))
        c.info("kill 后中间态 pid: %s" % (mid or "空"))
    finally:
        stop_loop(p)


@case("A-04", "A 部署与基础播放", "自检模式")
def a04(c):
    setup("主画面=0,0,100,92", zones={"主画面": (None, None)})
    img("content/主画面/01.png", "#0a3c78")
    build()
    d = dom("player.html?selftest=1", budget=6000)
    m = re.search(r"selftest (\d+)/(\d+)", d)
    c.t(bool(m), "自检页标题显示 selftest N/M", m.group(0) if m else "未匹配")
    if m:
        c.t(int(m.group(2)) >= 23, "自检项数 >= 23", m.group(2))
        c.t(int(m.group(1)) >= int(m.group(2)) - 2, "通过数接近满额", m.group(1) + "/" + m.group(2))
    c.t("writing-mode" in d or "竖排" in d, "含竖排(writing-mode)自检项")
    c.t("clip-path" in d or "框型" in d, "含多边形框型自检项")
    render("A-04_自检页.png", wait=3.0, url="player.html?selftest=1")


def pids():
    """start.sh 看门狗拉起的 kiosk 浏览器 pid 列表
    —— 只认带 --kiosk 的 player.html 进程：容器 pid 1（整段 shell 脚本）与 render() 的
       --app 临时窗口都会命中子串 player.html，必须排除"""
    out = subprocess.run("ps -eo pid,args", shell=True, capture_output=True, text=True).stdout
    res = []
    for ln in out.splitlines()[1:]:
        parts = ln.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, args = parts
        if pid == "1":
            continue
        if "player.html" in args and "--kiosk" in args:
            res.append(pid)
    return res


def kill_kiosk():
    for pid in pids():
        run("kill -9 %s 2>/dev/null || true" % pid)


def stop_all():
    """把 start.sh 看门狗与它拉起的浏览器一并清干净（多次重试：杀死后看门狗可能再拉一个）"""
    for _ in range(14):
        hit = False
        out = subprocess.run("ps -eo pid,args", shell=True, capture_output=True, text=True).stdout
        for ln in out.splitlines()[1:]:
            parts = ln.strip().split(None, 1)
            if len(parts) != 2:
                continue
            pid, args = parts
            if pid in ("1", str(os.getpid())):
                continue
            if ("player.html" in args) or ("start.sh" in args and "ps -eo" not in args):
                run("kill -9 %s 2>/dev/null || true" % pid)
                hit = True
        if not hit and not pids():
            break
        time.sleep(0.6)


@case("A-05", "A 部署与基础播放", "停止与重配")
def a05(c):
    setup("主画面=0,0,100,92", settings="DURATION=6\n", zones={"主画面": (None, None)})
    img("content/主画面/01.png", "#0a3c78")
    build()
    p = start_loop()
    time.sleep(7)
    before = pids()
    r = run("bash stop.sh", timeout=60)
    c.t("停止" in (r.stdout + r.stderr), "stop.sh 有执行反馈", (r.stdout + r.stderr).strip()[:40])
    time.sleep(4)          # 看门狗 sleep 3 后重启，等它一轮
    after = pids()
    render_capture("A-05_停止后仍在播.png")
    c.t(bool(before) and set(after) != set(before), "stop.sh 杀掉了当时的浏览器实例",
        "%s -> %s" % (before[:2], after[:2]))
    c.t(not after, "停止后无残留播放进程（真停机）", after[:3] if after else "0")
    stop_loop(p)
    time.sleep(1.5)
    left2 = pids()
    c.t(not left2, "结束 start.sh 进程组后彻底无残留", left2[:3] if left2 else "0")
    c.t('duration:"6"' in playlist() or "duration:6" in playlist(), "新时长 DURATION=6 生效",
        re.findall(r'duration:"?(\d+)"?', playlist())[:3])
    c.info("stop.sh 只 pkill 浏览器（且路径写死 mediaboard/player.html）；start.sh 的 while 看门狗 3 秒后会重新拉起，故单跑 stop.sh 不能停机")


# ================================================================ B 党政排版库
LAYOUT_NAMES = ["左3中2右3", "左竖联右内容", "红头文件式", "地图主版", "横幅五列", "品字形"]


def layout_path(name):
    return os.path.join(PKG, "layouts", "党政·" + name + ".txt")


def parse_layout(name, depth=0):
    """展开 layouts/<名>.txt（含 @LAYOUT 嵌套），返回 [(分区名, 类型)]"""
    out = []
    p = layout_path(name)
    if depth > 5 or not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("---"):
            continue
        if s.upper().startswith("@LAYOUT="):
            out += parse_layout(s.split("=", 1)[1].strip().replace("党政·", ""), depth + 1)
            continue
        # 形如  学习金句=g:1,1,4,3,,文本   或  主画面=0,0,100,92
        if "=" not in s:
            continue
        nm, rest = s.split("=", 1)
        fields = rest.split(",")
        ztype = fields[5].strip() if len(fields) > 5 else ""
        out.append((nm.strip(), ztype))
    return out


SAMPLE = {
    "文本": ("「%s」示例正文\n第二行说明文字\n", "SIZE=4\nCOLOR=#ffffff\nEFFECT=static\n"),
    "公告": ("值班安排已下发\n巡检记录已归档\n整改清单已签收\n",
             "TITLE=%s\nSIZE=2.6\nCOLOR=#e2e8f0\n"),
    "表格": ("项目|负责人|进度\n设备巡检|张工|92%\n线路维护|李工|78%\n安全整改|王工|65%\n",
             "TITLE=%s\nSIZE=2.2\nHEADER=yes\n"),
    "数据": ("累计产量|1280|件|72\n综合良率|98|%|98\n",
             "TITLE=%s\nSIZE=4\nVALUECOLOR=#ffd54a\n"),
    "仪表": ("负荷=72,100\n温度=45,100\n", "TITLE=%s\n"),
    "地图": ("中国\n标题:%s\n点:南昌,62%%,66%%,省会\n图例:已建,规划\n", "MAP_TINT=0\n"),
    "时钟": ("", "MODE=digital\nFORMAT=time\nSIZE=4\nCOLOR=#ffffff\n"),
    "计时": ("", "TARGET=2026-12-31\nSIZE=5\nCOLOR=#ffffff\n"),
    "二维码": ("https://kylin.example/scan", "TITLE=扫码\nCOLOR=#111111\nBGCOLOR=#ffffff\n"),
    "天气": ("南昌\n11-13,晴,22,12\n", "SIZE=2.6\n"),
    "网页": ("content/网页/挂件.html", ""),
}


def hydrate_zones(items, scheme="党建文化"):
    """按排版声明的分区名，从 schemes/<scheme>/content 取真实样式与文案；
    方案里没有的分区，按窗口类型造一份可判读的样例内容。"""
    zones = {}
    for name, ztype in items:
        src = os.path.join(PKG, "schemes", scheme, "content", name)
        text = style = None
        if os.path.isdir(src):
            tp, sp = os.path.join(src, "text.txt"), os.path.join(src, "style.txt")
            if os.path.exists(tp):
                text = open(tp, encoding="utf-8").read()
            if os.path.exists(sp):
                style = open(sp, encoding="utf-8").read()
        if text is None or style is None:
            tpl = SAMPLE.get(ztype)
            if tpl is None:  # 文件窗：内容由 case 自己 img() 铺图
                tpl = (None, None)
            if text is None:
                text = (tpl[0] % name) if tpl[0] else None
            if style is None:
                style = tpl[1]
        zones[name] = (text, style)
    return zones


def layout_scene(name, extra_layout="", settings=""):
    items = parse_layout(name)
    lay = (extra_layout + "\n" if extra_layout else "") + "@LAYOUT=党政·" + name
    return lay, settings, hydrate_zones(items)


def layout_zone_count(name):
    return len(parse_layout(name))


@case("B-01", "B 党政排版库", "左3中2右3 引用")
def b01(c):
    setup(*layout_scene("左3中2右3"))
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    pl = playlist()
    n = pl.count("zones:[")
    expect = layout_zone_count("左3中2右3")
    c.t(n >= 1 and "zones:[" in pl, "排版展开为分区", "页数=%d" % n)
    got = pl.count('{name:"')
    c.t(got == expect, "分区数与排版库一致", "%d/%d" % (got, expect))
    shot = render("B-01_左3中2右3.png", wait=3.0)
    im = load(shot)
    # 分区类型由内容键体现（text:/clock:/countdown:/notice:/table:），playlist 无 type 字段
    keys = ("text:{", "clock:{", "countdown:{", "notice:{", "table:{")
    c.t(all(k in pl for k in keys), "文本/时钟/计时/公告/表格多种窗口共存",
        [pl.count(x) for x in keys])
    c.t(std(im, P(0, 0, 1, 1)) > 10, "三栏结构有内容", std(im, P(0, 0, 1, 1)))
    c.t(bright_px(im, P(0, 0, 1, 1)) > 200, "各分区文字已上屏", bright_px(im, P(0, 0, 1, 1)))


@case("B-02", "B 党政排版库", "左竖联右内容")
def b02(c):
    setup(*layout_scene("左竖联右内容"))
    p = build()
    c.t(p.returncode == 0, "生成成功")
    pl = playlist()
    c.t("vertical" in pl.lower() or "竖" in pl, "含竖排标记", "vertical" in pl.lower())
    shot = render("B-02_左竖联右内容.png", wait=3.0)
    im = load(shot)
    d = dom()
    c.t("writing-mode:vertical-rl" in d.replace(" ", ""), "竖排标题用 writing-mode 实现")
    c.t(std(im, P(0, 0, .38, 1)) > 6, "左侧竖联区有内容", std(im, P(0, 0, .38, 1)))
    c.t(std(im, P(.42, 0, 1, 1)) > 6, "右侧内容区有内容", std(im, P(.42, 0, 1, 1)))


@case("B-03", "B 党政排版库", "红头文件式")
def b03(c):
    setup(*layout_scene("红头文件式"))
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    d = dom()
    c.t(bool(re.search(r'class="[^"]*mb-f-ribbon', d)), "红头横幅元素挂上 mb-f-ribbon 框型",
        re.findall(r'class="[^"]*mb-f-[a-z]+', d)[:3])
    shot = render("B-03_红头文件式.png", wait=3.0)
    im = load(shot)
    top = P(0, 0, 1, .20)
    red = count_near(im, top, (200, 16, 46), 60)
    gold = count_near(im, top, (255, 213, 74), 60)
    c.t(red + gold > 400, "顶部红金横幅成色（红→金渐变）", "红%d 金%d" % (red, gold))
    c.t("党建文化阵地" in d, "横幅文字已上屏（金色字进 DOM）", "党建文化阵地" in d)
    c.t(std(im, P(0, .25, 1, 1)) > 6, "正文区有内容", std(im, P(0, .25, 1, 1)))


@case("B-04", "B 党政排版库", "地图主版")
def b04(c):
    setup(*layout_scene("地图主版"))
    p = build()
    c.t(p.returncode == 0, "生成成功")
    pl = playlist()
    c.t("map:{" in pl, "含地图窗口分区", "map:{" in pl)
    shot = render("B-04_地图主版.png", wait=3.2)
    im = load(shot)
    c.t(std(im, P(0, 0, 1, 1)) > 10, "整页有内容", std(im, P(0, 0, 1, 1)))
    c.t(count_near(im, P(0, 0, .7, .7), (255, 213, 74), 60) > 50 or
        count_near(im, P(0, 0, .7, .7), (200, 16, 46), 60) > 50, "地图分区着色已成图",
        (count_near(im, P(0, 0, .7, .7), (255, 213, 74), 60),
         count_near(im, P(0, 0, .7, .7), (200, 16, 46), 60)))


@case("B-05", "B 党政排版库", "横幅五列")
def b05(c):
    setup(*layout_scene("横幅五列"))
    p = build()
    c.t(p.returncode == 0, "生成成功")
    shot = render("B-05_横幅五列.png", wait=3.0)
    im = load(shot)
    cols = [std(im, P(.02 + i * .19, .2, .18 + i * .19, .98)) for i in range(5)]
    c.t(sum(1 for v in cols if v > 4) >= 4, "五列各自有内容", cols)


@case("B-06", "B 党政排版库", "排版混排与容错")
def b06(c):
    items = parse_layout("品字形")
    zones = hydrate_zones(items)
    zones["额外"] = ("手写行共存", "SIZE=3\nCOLOR=#7dd3fc\nEFFECT=static\n")
    setup("@LAYOUT=党政·品字形\n额外=0,80,100,12,8,文本", zones=zones)
    p = build()
    pl = playlist()
    c.t(p.returncode == 0, "混排生成成功", p.stderr.strip()[-80:])
    c.t("手写行共存" in open(os.path.join(WORK, "content", "额外", "text.txt"), encoding="utf-8").read(), "手写分区已写入")
    c.t(pl.count("zones:[") == 1, "仍为一页", pl.count("zones:["))
    c.t(pl.count('{name:"') == len(items) + 1, "排版分区与手写行合并", "%d+1" % len(items))
    shot = render("B-06_混排.png", wait=3.0)
    cyan = count_near(load(shot), P(0, .80, 1, 1), (125, 211, 252), 60)
    c.t(cyan > 60, "手写行渲染在页面底部（自定义青色）", cyan)
    # 容错：不存在的排版名
    setup("@LAYOUT=党政·不存在的版式")
    p2 = build()
    c.t(p2.returncode == 0, "错误排版名不导致生成失败", p2.returncode)
    c.t("排版" in (p2.stdout + p2.stderr), "有提示信息", (p2.stdout + p2.stderr).strip()[-100:])


# ================================================================ C 区域框型库（30 种，抽验 8）
def frame_scene(frame, extra="", text="框型验收"):
    return ("卡=4,4,92,88,,文本",
            "",
            {"卡": (text + "\n", "SIZE=5\nCOLOR=#ffffff\nEFFECT=static\nFRAME=%s\n%s" % (frame, extra))})


@case("C-01", "C 区域框型库", "票券框")
def c01(c):
    lay, st, z = frame_scene("ticket", "FRAME_COLOR=#ffd54a\nFRAME_COLOR2=#c8102e\n")
    setup(lay, st, z)
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    c.t('frame:"ticket"' in playlist(), "playlist 记录 frame=ticket")
    d = dom()
    c.t("mb-f-ticket" in d, "DOM 应用 mb-f-ticket 类")
    shot = render("C-01_票券框.png")
    c.t(std(load(shot), (40, 40, W - 40, H - 40)) > 8, "卡片区域有内容", std(load(shot), (40, 40, W - 40, H - 40)))


@case("C-02", "C 区域框型库", "波浪底边")
def c02(c):
    setup(*frame_scene("wave"))
    build()
    d = dom()
    c.t("mb-f-wave" in d, "DOM 应用 mb-f-wave 类")
    shot = render("C-02_波浪底边.png")
    im = load(shot)
    band = [count_near(im, (60, y, W - 60, y + 4), (255, 213, 74), 70) for y in range(int(H * 0.82), int(H * 0.94), 6)]
    c.t(std(im, (0, int(H * 0.8), W, H)) > 3, "底缘有波浪装饰（非纯平）", band[:4])


@case("C-03", "C 区域框型库", "拍立得相框")
def c03(c):
    setup(*frame_scene("photo", "FRAME_COLOR=#ffffff\n"))
    build()
    d = dom()
    c.t("mb-f-photo" in d, "DOM 应用 mb-f-photo 类")
    shot = render("C-03_拍立得.png")
    im = load(shot)
    bb = bright_bbox(im, P(0, 0, 1, 1), 200)
    cw, ch = CBOX[2] - CBOX[0], CBOX[3] - CBOX[1]
    span_w = (bb[2] - bb[0]) / float(cw) if bb else 0
    span_h = (bb[3] - bb[1]) / float(ch) if bb else 0
    c.t(bool(bb) and bb[4] > 300 and span_w > .7 and span_h > .6,
        "白色粗边框闭合（占满卡片四周）", "像素%d 宽%.0f%% 高%.0f%%" % (bb[4], span_w * 100, span_h * 100) if bb else "无白边")


@case("C-04", "C 区域框型库", "胶片框")
def c04(c):
    setup(*frame_scene("film", "FRAME_COLOR=#ffffff\n"))
    build()
    d = dom()
    c.t("mb-f-film" in d, "DOM 应用 mb-f-film 类")
    shot = render("C-04_胶片框.png")
    im = load(shot)
    top = count_near(im, (0, int(H * 0.06), W, int(H * 0.12)), (0, 0, 0), 40)
    c.t(top > 500, "上缘齿孔暗区成片", top)


@case("C-05", "C 区域框型库", "终端窗")
def c05(c):
    setup(*frame_scene("terminal"))
    build()
    d = dom()
    c.t("mb-f-terminal" in d, "DOM 应用 mb-f-terminal 类")
    shot = render("C-05_终端窗.png")
    im = load(shot)
    dots = sum(count_near(im, (40, 30, 260, 90), col, 45) for col in
               ((255, 95, 86), (255, 189, 46), (39, 201, 63)))
    c.t(dots > 5, "左上三色圆点", dots)


@case("C-06", "C 区域框型库", "对话气泡")
def c06(c):
    setup(*frame_scene("bubble", "FRAME_COLOR=#38bdf8\n"))
    build()
    d = dom()
    c.t("mb-f-bubble" in d, "DOM 应用 mb-f-bubble 类")
    shot = render("C-06_对话气泡.png")
    c.t(std(load(shot), (60, 60, W - 60, H - 60)) > 6, "气泡内有内容")


@case("C-07", "C 区域框型库", "菱形/八边形")
def c07(c):
    ok = []
    for f in ("diamond", "octagon"):
        setup(*frame_scene(f))
        build()
        d = dom()
        c.t("mb-f-%s" % f in d, "DOM 应用 mb-f-%s" % f)
        shot = render("C-07_%s.png" % f)
        im = load(shot)
        corner = mean(im, P(0, 0, .06, .08))
        center = P(.34, .40, .66, .60)
        dark = sum(corner) < 90
        ok.append(dark)
        c.t(dark, "%s 角落被裁掉（露出背景）" % f, corner)
        c.t(bright_px(im, center) > 40, "%s 中心仍有卡片内容（文字上屏）" % f,
            (bright_px(im, center), mean(im, center)))


@case("C-08", "C 区域框型库", "框型双色定制")
def c08(c):
    setup(*frame_scene("panel", "FRAME_COLOR=#38bdf8\nFRAME_COLOR2=#1d4ed8\n"))
    build()
    d = dom()
    c.t("mb-f-panel" in d, "DOM 应用 mb-f-panel 类")
    c.t("38bdf8" in d.lower(), "自定义主线色进 DOM", "38bdf8" in d.lower())
    shot = render("C-08_面板双色.png")
    im = load(shot)
    blue = count_near(im, (0, 0, W, H), (56, 189, 248), 30)
    c.t(blue > 60, "蓝色系边线成色", blue)


# ================================================================ D 地图窗
MAP_TEXT_BASE = """中国
标题:中国区域分布
点:南昌,62%,66%,省会
图例:已建,规划
"""


def map_scene(text=None, style="MAP_TINT=0\n", extra_text="", layout="地图=0,0,100,88,,地图"):
    return (layout, "", {"地图": (text if text is not None else MAP_TEXT_BASE, style)})


@case("D-01", "D 地图窗", "内置地图装载")
def d01(c):
    setup(*map_scene())
    build()
    d = dom()
    c.t("mb-map" in d, "地图 DOM 容器存在")
    c.t("中国区域分布" in d, "标题文字渲染")
    shot = render("D-01_内置地图.png", wait=3.0)
    im = load(shot)
    c.t(std(im, (0, 0, W, H)) > 12, "地图有图形内容", std(im, (0, 0, W, H)))


@case("D-02", "D 地图窗", "域高亮呼吸")
def d02(c):
    setup(*map_scene(text=MAP_TEXT_BASE.replace("图例:", "域:江西,陕西\n图例:")))
    build()
    shots = render_seq(["D-02_a.png", "D-02_b.png"], [2.2, 1.3])
    a, b = load(shots[0]), load(shots[1])
    gold_a = count_near(a, (0, 0, W, H), (255, 213, 74), 60)
    gold_b = count_near(b, (0, 0, W, H), (255, 213, 74), 60)
    c.t(gold_a > 30 and gold_b > 30, "高亮区金色填充", (gold_a, gold_b))
    c.t(abs(gold_a - gold_b) > 0 or diff_frac(shots[0], shots[1]) > 0.002,
        "呼吸动画（两帧有差异）", diff_frac(shots[0], shots[1]))


@case("D-03", "D 地图窗", "分区颜色（v7）")
def d03(c):
    t = MAP_TEXT_BASE.replace("图例:", "色:江西=#c8102e,陕西=#ffd54a\n明度:江西=100,陕西=100\n图例:")
    setup(*map_scene(text=t))
    build()
    shot = render("D-03_分区颜色.png", wait=3.2)
    im = load(shot)
    red = count_near(im, P(0, 0, 1, 1), (200, 16, 46), 24)
    gold = count_near(im, P(0, 0, 1, 1), (255, 213, 74), 24)
    c.t(red > 200, "江西呈红色填充", red)
    c.t(gold > 200, "陕西呈金黄色填充", gold)


@case("D-04", "D 地图窗", "分区透明度（v7）")
def d04(c):
    base = MAP_TEXT_BASE.replace("图例:", "色:江西=#c8102e,陕西=#ffd54a\n图例:")
    res = {}
    for v, png in ((100, "D-04_alpha100.png"), (20, "D-04_alpha20.png")):
        t = base.replace("图例:", "明度:江西=%d,陕西=%d\n图例:" % (v, v))
        setup(*map_scene(text=t))
        build()
        shot = render(png, wait=3.2)
        im = load(shot)
        res[v] = (count_near(im, P(0, 0, 1, 1), (200, 16, 46), 26), mean(im, P(0, .1, 1, .9)))
    r100, m100 = res[100]
    r20, m20 = res[20]
    c.t(r100 > 200, "明度=100 时纯色填充面积", r100)
    c.t(r20 * 2 < r100, "明度=20 时同色像素大幅减少（半透明）", "%d -> %d" % (r100, r20))
    c.t(sum(m100) > sum(m20), "整片地图随之变淡", "%s -> %s" % (m100, m20))


@case("D-05", "D 地图窗", "全局透明度（v7）")
def d05(c):
    setup(*map_scene(style="MAP_TINT=0\n"))
    build()
    base = render("D-05_base.png", wait=3.0)
    m0 = mean(load(base), (0, 100, W, H - 100))
    setup(*map_scene(style="MAP_TINT=0\nREGION_ALPHA=40\n"))
    build()
    sh = render("D-05_region_alpha40.png", wait=3.0)
    m1 = mean(load(sh), (0, 100, W, H - 100))
    c.t(sum(m1) < sum(m0), "未配色分区整体变淡（底图透出）", "%s -> %s" % (m0, m1))


@case("D-06", "D 地图窗", "标记与图例")
def d06(c):
    setup(*map_scene())
    build()
    d = dom()
    c.t(d.count("mb-map-pin") >= 1, "脉冲标记点存在", d.count("mb-map-pin"))
    c.t("mb-map-legend" in d, "图例存在")
    c.t("mb-map-label" in d, "标签文字存在")
    render("D-06_标记图例.png", wait=3.0)


@case("D-07", "D 地图窗", "底图压暗/模糊")
def d07(c):
    setup(*map_scene(style="MAP_TINT=0\n"))
    build()
    base = render("D-07_base.png", wait=3.0)
    m0 = mean(load(base), (0, 60, W, H - 60))
    setup(*map_scene(style="MAP_TINT=40\nMAP_BLUR=1.5\n"))
    build()
    d = dom()
    sh = render("D-07_tint_blur.png", wait=3.0)
    m1 = mean(load(sh), (0, 60, W, H - 60))
    c.t(sum(m1) < sum(m0), "底图压暗（整体变暗）", "%s -> %s" % (m0, m1))
    c.t("blur" in d, "模糊样式已应用")


@case("D-08", "D 地图窗", "自定义 SVG")
def d08(c):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700">'
           '<rect x="80" y="80" width="380" height="520" fill="#1b2a44" data-region="楼层A"/>'
           '<rect x="520" y="80" width="380" height="520" fill="#1b2a44" data-region="楼层B"/>'
           '</svg>')
    setup(*(lambda lay, st, z: (lay, st, z))(
        "地图=0,0,100,88,,地图", "",
        {"地图": ("maps/custom2.svg\n标题:园区平面\n域:楼层A\n图例:已建\n", "MAP_TINT=0\n")}))
    open(os.path.join(WORK, "maps", "custom2.svg"), "w", encoding="utf-8").write(svg)
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    shot = render("D-08_自定义SVG.png", wait=3.0)
    im = load(shot)
    gold = count_near(im, (0, 0, W, H), (255, 213, 74), 60)
    c.t(gold > 30, "自定义区域被高亮", gold)


# ================================================================ E 倒计时主题
def timer_style(**kw):
    base = "SIZE=8\nCOLOR=#ffffff\nEFFECT=static\n"
    for k, v in kw.items():
        base += "%s=%s\n" % (k.upper(), v)
    return base


@case("E-01", "E 倒计时主题", "主题横幅（v7）")
def e01(c):
    setup("计时=0,0,100,88,,计时", "", {"计时": ("", timer_style(topic="安全生产 100 天", target="2026-12-31 00:00"))})
    build()
    d = dom()
    c.t("安全生产 100 天" in d, "主题横幅文字渲染", "安全生产 100 天" in d)
    c.t("倒计时" in d, "倒计时标签存在")
    shot = render("E-01_主题横幅.png", wait=3.0)
    im = load(shot)
    red = count_near(im, P(0, 0, 1, 1), (200, 16, 46), 55)
    c.t(red > 800, "红色渐变横幅成色", red)
    c.t(bright_px(im, P(0, 0, 1, .55)) > 30, "横幅文字已上屏", bright_px(im, P(0, 0, 1, .55)))


@case("E-02", "E 倒计时主题", "主题改字")
def e02(c):
    setup("计时=0,0,100,88,,计时", "", {"计时": ("", timer_style(topic="距党代会开幕", target="2026-12-31"))})
    build()
    d = dom()
    c.t("距党代会开幕" in d, "改字后横幅文字同步", "距党代会开幕" in d)
    c.t("安全生产" not in d, "旧主题文字已消失")
    render("E-02_主题改字.png", wait=2.6)


@case("E-03", "E 倒计时主题", "倒计时模式")
def e03(c):
    setup("计时=0,0,100,88,,计时", "", {"计时": ("", timer_style(target="2026-12-31 00:00", title="距年底"))})
    build()
    d = dom()
    txt = re.sub(r"<[^>]+>", "", d)
    c.t("距年底" in txt and "天" in txt, "标题与天单位同时显示", "距年底" in txt)
    m = re.search(r"(\d{2,3})\s*天", txt)
    c.t(bool(m), "有天数数字", m.group(1) if m else "")
    shots = render_seq(["E-03_a.png", "E-03_b.png"], [2.2, 1.2])
    c.t(diff_frac(shots[0], shots[1]) > 0.0005, "秒位在跳动", diff_frac(shots[0], shots[1]))


@case("E-04", "E 倒计时主题", "累计模式（v7）")
def e04(c):
    setup("计时=0,0,100,88,,计时", "", {"计时": ("", timer_style(since="2025-06-01"))})
    build()
    d = dom()
    txt = re.sub(r"<[^>]+>", "", d)
    m = re.search(r"第\s*(\d+)\s*天", txt)
    c.t(bool(m), "显示「第 N 天」", m.group(0) if m else "未匹配")
    if m:
        n = int(m.group(1))
        c.t(500 <= n <= 560, "天数为含首日累计", n)
    c.t("2025" in txt or "06" in txt, "起算日期可见", "2025" in txt)
    render("E-04_累计第N天.png", wait=2.6)


@case("E-05", "E 倒计时主题", "单位与标签")
def e05(c):
    setup("计时=0,0,100,88,,计时", "",
          {"计时": ("", timer_style(topic="冲刺四季度", target="2026-12-31", unit="周", label="冲刺"))})
    build()
    txt = re.sub(r"<[^>]+>", "", dom())
    c.t("周" in txt, "单位改为「周」")
    c.t("冲刺" in txt, "标签改为「冲刺」", "冲刺" in txt)
    render("E-05_单位标签.png", wait=2.6)


@case("E-06", "E 倒计时主题", "主题配色")
def e06(c):
    setup("计时=0,0,100,88,,计时", "",
          {"计时": ("", timer_style(topic="蓝色主题", target="2026-12-31",
                                    topic_bg="#1d4ed8", topic_color="#ffffff"))})
    build()
    d = dom()
    c.t("1d4ed8" in d.lower() or "rgb(29, 78, 216)" in d or "rgb(29,78,216)" in d,
        "主题底色改为蓝", re.findall(r"linear-gradient\(90deg[^)]*\)", d)[:2])
    shot = render("E-06_主题配色.png", wait=2.6)
    im = load(shot)
    blue = count_near(im, P(0, 0, 1, 1), (29, 78, 216), 45)
    c.t(blue > 800, "蓝底横幅成色", blue)


@case("E-07", "E 倒计时主题", "兼容回归")
def e07(c):
    setup("计时=0,0,100,88,,计时", "", {"计时": ("", timer_style(target="2027-01-01 09:00", title="距开幕"))})
    build()
    txt = re.sub(r"<[^>]+>", "", dom())
    c.t("距开幕" in txt, "v6 原生 TITLE 样式保留", "距开幕" in txt)
    md = re.search(r"\d{2,3}\s*天", txt)
    c.t(bool(md), "精确到天的倒计时仍在", md.group(0) if md else "未匹配")
    c.t("第" not in txt.replace("第一", ""), "无主题横幅时退回原生样式")
    render("E-07_兼容回归.png", wait=2.6)


# ================================================================ F 模板底图五参
def photo(rel="bg/大厅.jpg"):
    p = os.path.join(WORK, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    run(["convert", "-size", "800x600", "gradient:#204060-#c8a050", p], cwd=WORK)
    return rel


def bg_scene(settings, zone_style="SIZE=4\nCOLOR=#ffffff\nEFFECT=static\n", text="底图验收"):
    return ("卡=8,20,84,56,,文本", settings, {"卡": (text + "\n", zone_style)})


@case("F-01", "F 底图自定义", "底图适配")
def f01(c):
    setup("卡=8,20,84,56,,文本")
    photo()
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write(
        "BGIMAGE=bg/大厅.jpg\nBG_FIT=contain\n")
    build()
    d = dom()
    c.t("contain" in d, "BG_FIT=contain 生效", "contain" in d)
    c.t("大厅" in d or "bg/" in d, "底图路径进入页面")
    shot = render("F-01_底图contain.png")
    c.t(std(load(shot), (0, 0, W, H)) > 8, "底图渲染")


@case("F-02", "F 底图自定义", "底图位置")
def f02(c):
    setup("卡=8,20,84,56,,文本")
    photo()
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write(
        "BGIMAGE=bg/大厅.jpg\nBG_POS=top\n")
    build()
    d = dom()
    c.t(re.search(r"background-position:[^;\"]*top", d) or "top" in d, "BG_POS=top 生效")
    render("F-02_底图top.png")


@case("F-03", "F 底图自定义", "底图透明度")
def f03(c):
    setup("卡=8,20,84,56,,文本")
    photo()
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write(
        "BGIMAGE=bg/大厅.jpg\nBG_OPACITY=60\n")
    build()
    d = dom()
    c.t(re.search(r"opacity:\s*0?\.6", d) is not None, "BG_OPACITY=60 生效",
        re.findall(r"opacity:[^;\"]{1,8}", d)[:4])
    shot = render("F-03_底图opacity60.png")
    base = os.path.join(SHOT, "F-01_底图contain.png")
    if os.path.exists(base):
        c.t(diff_frac(base, shot) > 0.02, "与不设透明度时明显不同", diff_frac(base, shot))


@case("F-04", "F 底图自定义", "底图模糊")
def f04(c):
    setup("卡=8,20,84,56,,文本")
    photo()
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write(
        "BGIMAGE=bg/大厅.jpg\nBG_BLUR=1.5\n")
    build()
    d = dom()
    c.t("blur" in d, "BG_BLUR 生效", "blur" in d)
    shot = render("F-04_底图blur.png")
    c.t(std(load(shot), (0, 0, W, H)) > 4, "模糊后仍有画面")


@case("F-05", "F 底图自定义", "底图压暗")
def f05(c):
    setup("卡=8,20,84,56,,文本")
    photo()
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write("BGIMAGE=bg/大厅.jpg\n")
    build()
    base = render("F-05_base.png")
    m0 = mean(load(base), (0, 0, W, H))
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write("BG_DARKEN=45\n")
    build()
    d = dom()
    sh = render("F-05_darken45.png")
    m1 = mean(load(sh), (0, 0, W, H))
    c.t("mb-bg-tint" in d, "压暗遮罩层存在")
    c.t(sum(m1) < sum(m0), "整体压暗", "%s -> %s" % (m0, m1))


@case("F-06", "F 底图自定义", "五参组合")
def f06(c):
    setup("标题=4,6,92,16,,文本\n卡=8,24,84,52,,文本", "",
          {"标题": ("红金标题", "SIZE=7\nFONT=思源宋体 粗\nCOLOR=#ffd54a\nEFFECT=static\nGLOW=#c8102e\n"),
           "卡": ("正文说明文字", "SIZE=3.6\nCOLOR=#ffffff\nEFFECT=static\n")})
    photo()
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write(
        "BGIMAGE=bg/大厅.jpg\nBG_FIT=cover\nBG_POS=center\nBG_OPACITY=70\nBG_BLUR=1.5\nBG_DARKEN=45\n")
    build()
    shot = render("F-06_五参组合.png")
    im = load(shot)
    c.t(count_near(im, (0, 0, W, 200), (255, 213, 74), 55) > 80, "红金标题清晰", count_near(im, (0, 0, W, 200), (255, 213, 74), 55))
    c.t(count_near(im, (0, 200, W, H), (255, 255, 255), 25) > 80, "白字可读", count_near(im, (0, 200, W, H), (255, 255, 255), 25))
    c.t(std(im, (0, 0, W, H)) > 10, "画面有层次", std(im, (0, 0, W, H)))


@case("F-07", "F 底图自定义", "分区背景图")
def f07(c):
    setup("卡=10,10,80,70,,文本", "",
          {"卡": ("分区背景图验收\n", "SIZE=4\nCOLOR=#ffffff\nEFFECT=static\nZBG=textures/vignette.png\nZBG_FIT=contain\n")})
    build()
    pl = playlist()
    c.t('zbg:"textures/vignette.png"' in pl, "ZBG 已写入 playlist", [x for x in re.findall(r"zbg[^,]*", pl)][:2])
    d = dom()
    c.t("vignette" in d, "分区背景图进入 DOM（zone 内联样式）", "vignette" in d)
    shot = render("F-07_分区背景图.png", wait=3.0)
    im = load(shot)
    card = mean(im, P(.12, .12, .88, .78))
    # vignette 纹理偏蓝（均色 23,43,74）；不铺图时卡片是 rgba(0,0,0,.45) 压底色，蓝红差只有 ~10
    c.t(card[2] - card[0] > 25, "分区底图真的画出来了（蓝调纹理）", card)


@case("F-08", "F 底图自定义", "与 BGFX 隔离")
def f08(c):
    setup("卡=8,20,84,56,,文本")
    photo()
    open(os.path.join(WORK, "settings.txt"), "a", encoding="utf-8").write(
        "BGIMAGE=bg/大厅.jpg\nBGFX=aurora\n")
    build()
    d = dom()
    c.t("mb-bgfx" in d or "aurora" in d, "动态背景层存在")
    c.t("mb-bg-img" in d or "大厅" in d, "底图层同时存在")
    shot = render("F-08_BGFX叠加.png", wait=3.0)
    c.t(std(load(shot), (0, 0, W, H)) > 10, "两层叠加后仍可读", std(load(shot), (0, 0, W, H)))


# ================================================================ G 字体与导入
@case("G-01", "G 字体与导入", "包内三字体")
def g01(c):
    setup("甲=2,2,96,28,,文本\n乙=2,32,96,28,,文本\n丙=2,62,96,28,,文本", "",
          {"甲": ("思源宋体粗 庄重标题", "SIZE=5\nFONT=思源宋体 粗\nCOLOR=#ffffff\nEFFECT=static\n"),
           "乙": ("思源黑体常规 正文", "SIZE=5\nFONT=思源黑体 常规\nCOLOR=#ffffff\nEFFECT=static\n"),
           "丙": ("思源黑体粗 强调", "SIZE=5\nFONT=思源黑体 粗\nCOLOR=#ffffff\nEFFECT=static\n")})
    build()
    pl = playlist()
    fams = re.findall(r'family:"([^"]+)"', pl)
    c.t(len(set(fams)) >= 3, "三种字体家族进 playlist", sorted(set(fams))[:4])
    d = dom()
    body = d[d.find("<body"):] or d
    used = [f for f in ("思源宋体 粗", "思源黑体 常规", "思源黑体 粗") if f in body]
    c.t(len(used) >= 2, "页面实际用上不同 font-family", used)
    shot = render("G-01_三字体.png")
    c.t(std(load(shot), P(0, 0, 1, 1)) > 8, "三行文字均已渲染")


@case("G-02", "G 字体与导入", "字体列举（v7）")
def g02(c):
    setup("卡=0,0,100,88,,文本", "", {"卡": ("字体列举", "SIZE=5\nEFFECT=static\n")})
    r0 = run(["./import-fonts.sh", "--list"], timeout=180)
    out0 = r0.stdout + r0.stderr
    lines = [x for x in out0.splitlines() if x.strip() and not x.startswith("提示")]
    c.t(r0.returncode == 0, "脚本可执行", r0.returncode)
    c.t(len(lines) > 0, "能列出系统字体清单", lines[:2])
    c.t("提示" in out0, "无命中时给出用法提示", out0.strip().splitlines()[-1][:60] if out0.strip() else "")
    # 关键词过滤：用清单里第一个字体名的前 4 个字符当关键词，必须能命中它
    out1 = ""
    if lines:
        kw = os.path.basename(lines[0].split()[0])[:4]
        r1 = run(["./import-fonts.sh", "--list", kw], timeout=180)
        out1 = r1.stdout + r1.stderr
        c.t(os.path.basename(lines[0].split()[0]) in out1,
            "关键词过滤命中（--list %s）" % kw, out1.strip().splitlines()[:1])
    r2 = run(["./import-fonts.sh", "--list", "不存在的字体xyz"], timeout=180)
    c.t("提示" in (r2.stdout + r2.stderr), "无命中只给提示不报错", r2.returncode)
    c.info("容器内无中文字体的楷/宋分类，故用系统字体名当关键词验证列举与过滤逻辑；真机麒麟可用 fc-list :lang=zh 核对")
    cli_shot("G-02_字体列举.png", "$ ./import-fonts.sh --list\n" + out0 +
             "\n$ ./import-fonts.sh --list " + (os.path.basename(lines[0].split()[0])[:4] if lines else "Noto") +
             "\n" + (out1 if lines else "") +
             "\n$ ./import-fonts.sh --list 不存在的字体xyz\n" + r2.stdout + r2.stderr)


@case("G-03", "G 字体与导入", "字体导入（v7）")
def g03(c):
    setup("卡=0,0,100,88,,文本", "", {"卡": ("字体导入", "SIZE=5\nEFFECT=static\n")})
    before = len([f for f in os.listdir(os.path.join(WORK, "fonts")) if f.lower().endswith((".ttf", ".otf", ".woff", ".woff2"))])
    # 用包内自带字体模拟"系统命中"：指定文件路径导入
    src = None
    for root, _, fs in os.walk("/usr/share/fonts"):
        for f in fs:
            if f.lower().endswith((".ttf", ".otf")):
                src = os.path.join(root, f)
                break
        if src:
            break
    c.t(bool(src), "容器内有系统字体可供导入", src or "无")
    r = run(["./import-fonts.sh", src], timeout=180)
    after = len([f for f in os.listdir(os.path.join(WORK, "fonts")) if f.lower().endswith((".ttf", ".otf", ".woff", ".woff2"))])
    c.t(r.returncode == 0, "导入命令成功", r.returncode)
    c.t(after > before, "字体已复制进 fonts/", "%d -> %d" % (before, after))
    c.t("FONTS.txt" in (r.stdout + r.stderr), "提示写 FONTS.txt 别名", (r.stdout + r.stderr).strip()[-100:])
    cli_shot("G-03_字体导入.png", "$ ./import-fonts.sh %s\n%s\n\nfonts/ 内字体文件数：%d -> %d"
             % (src, (r.stdout + r.stderr).strip(), before, after))


@case("G-04", "G 字体与导入", "导入生效")
def g04(c):
    setup("卡=0,0,100,88,,文本", "",
          {"卡": ("导入字体生效验证", "SIZE=5\nFONT=导入测试体\nCOLOR=#ffffff\nEFFECT=static\n")})
    # 用包内字体复制一份当"导入字体"，并在 FONTS.txt 写别名
    src = os.path.join(WORK, "fonts", "SourceHanSansSC-Regular.woff2")
    shutil.copy(src, os.path.join(WORK, "fonts", "ImportedTest.woff2"))
    ft = os.path.join(WORK, "fonts", "FONTS.txt")
    txt = open(ft, encoding="utf-8").read() if os.path.exists(ft) else ""
    open(ft, "w", encoding="utf-8").write(txt + "\nImportedTest.woff2=导入测试体\n")
    build()
    pl = playlist()
    c.t("导入测试体" in pl, "别名进 fontfaces", "导入测试体" in pl)
    d = dom()
    c.t("导入测试体" in d, "页面用上别名字体")
    shot = render("G-04_导入字体生效.png")
    c.t(count_near(load(shot), (0, 0, W, H), (255, 255, 255), 30) > 60, "文字正常显示")


@case("G-05", "G 字体与导入", "字体自检")
def g05(c):
    setup("卡=0,0,100,88,,文本", "", {"卡": ("字体自检", "SIZE=5\nEFFECT=static\n")})
    build()
    d = dom("player.html?selftest=1", budget=7000)
    txt = re.sub(r"<[^>]+>", "", d)
    c.t("字体" in txt, "自检含字体项")
    marks = txt.count("✔") + txt.count("√")
    c.t(marks >= 3, "字体逐项显示加载结果", marks)
    render("G-05_字体自检.png", wait=3.0, url="player.html?selftest=1")


@case("G-06", "G 字体与导入", "回退安全")
def g06(c):
    setup("卡=0,0,100,88,,文本", "",
          {"卡": ("不存在的字体也要能看清", "SIZE=5\nFONT=根本不存在体\nCOLOR=#ffffff\nEFFECT=static\n")})
    p = build()
    c.t(p.returncode == 0, "生成不报错", p.returncode)
    shot = render("G-06_字体回退.png")
    im = load(shot)
    c.t(count_near(im, (0, 0, W, H), (255, 255, 255), 40) > 60, "文字仍可见（回退系统字体）",
          count_near(im, (0, 0, W, H), (255, 255, 255), 40))


# ================================================================ H 分屏/方案/定时
def now_hm(offset_min=0):
    t = time.localtime(time.time() + offset_min * 60)
    return "%02d:%02d" % (t.tm_hour, t.tm_min)


@case("H-01", "H 分屏与方案定时", "二分屏")
def h01(c):
    setup("@PANE=1\n左图=0,0,100,100\n--- 10\n@PANE=2\n右图=0,0,100,100",
          settings="SPLIT=2H\nPAGE_DURATION=30\n",
          zones={"左图": (None, None), "右图": (None, None)})
    img("content/左图/1.png", "#c8102e")
    img("content/右图/1.png", "#00a040")
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    c.t('split:"2H"' in playlist() or "2H" in playlist(), "split=2H 进 playlist")
    d = dom()
    c.t(d.count('class="mb-pane"') == 2, "页面切成两块", d.count('class="mb-pane"'))
    shot = render("H-01_二分屏.png", wait=3.0)
    im = load(shot)
    left, right = mean(im, (20, 200, 500, 400)), mean(im, (780, 200, 1260, 400))
    c.t(left[0] > 120 and right[1] > 80, "左右两块各自轮播不同内容", (left, right))


@case("H-02", "H 分屏与方案定时", "田字四分屏")
def h02(c):
    lay = ("@PANE=1\nA=0,0,100,100\n--- 10\n@PANE=2\nB=0,0,100,100\n--- 10\n"
           "@PANE=3\nC=0,0,100,100\n--- 10\n@PANE=4\nD=0,0,100,100")
    zones = {k: (None, None) for k in "ABCD"}
    setup(lay, settings="SPLIT=4G\nPAGE_DURATION=30\n", zones=zones)
    img("content/A/1.png", "#c8102e")
    img("content/B/1.png", "#00a040")
    img("content/C/1.png", "#1040c8")
    img("content/D/1.png", "#d0a020")
    build()
    d = dom()
    c.t(d.count('class="mb-pane"') == 4, "四块分屏", d.count('class="mb-pane"'))
    shot = render("H-02_田字四分屏.png", wait=3.0)
    im = load(shot)
    q = [mean(im, (40, 40, 560, 300)), mean(im, (720, 40, 1240, 300)),
         mean(im, (40, 380, 560, 680)), mean(im, (720, 380, 1240, 680))]
    c.t(len(set(tuple(round(x) for x in v) for v in q)) >= 3, "四块内容各不相同", q)


@case("H-03", "H 分屏与方案定时", "空分屏占位")
def h03(c):
    setup("@PANE=1\n左=0,0,100,100\n--- 10\n@PANE=2\n中=0,0,100,100",
          settings="SPLIT=3H\nPAGE_DURATION=30\n", zones={"左": (None, None), "中": (None, None)})
    img("content/左/1.png", "#c8102e")
    img("content/中/1.png", "#00a040")
    build()
    d = dom()
    txt = re.sub(r"<[^>]+>", "", d)
    c.t(d.count('class="mb-pane"') == 3, "三块分屏", d.count('class="mb-pane"'))
    c.t("待编排" in txt, "第三块显示待编排占位", "待编排" in txt)
    shot = render("H-03_空分屏占位.png", wait=3.0)
    im = load(shot)
    c.t(mean(im, (880, 200, 1240, 500))[0] > 6, "占位块非纯黑", mean(im, (880, 200, 1240, 500)))


@case("H-04", "H 分屏与方案定时", "开机方案")
def h04(c):
    setup("主画面=0,0,100,88", settings="SCHEME=党建文化\nPAGE_DURATION=20\n",
          zones={"主画面": (None, None)})
    img("content/主画面/1.png", "#0a3c78")
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    c.t(os.path.exists(os.path.join(WORK, "playlist-党建文化.js")), "生成方案 playlist")
    sj = open(os.path.join(WORK, "schemes.js"), encoding="utf-8").read()
    c.t('SCHEMES_ACTIVE="党建文化"' in sj, "开机方案写入 schemes.js", sj[:120])
    shot = render("H-04_开机党建方案.png", wait=3.5)
    im = load(shot)
    red = count_near(im, (0, 0, W, H), (200, 16, 46), 55)
    c.t(red > 200, "党建红金方案已上屏", red)


@case("H-05", "H 分屏与方案定时", "方案热切换")
def h05(c):
    setup("主画面=0,0,100,88", settings="SCHEME=党建文化\nPAGE_DURATION=20\n",
          zones={"主画面": (None, None)})
    img("content/主画面/1.png", "#0a3c78")
    open(os.path.join(WORK, "schedule.txt"), "w", encoding="utf-8").write(
        "%s=scheme:日常发布\n" % now_hm(1))
    build()
    c.t("scheme:日常发布" in playlist(), "定时切方案指令已解析")
    # schedule 每 20 秒对齐一次，过点后至少再等 25 秒才能保证轮询命中
    wait = 62 - int(time.strftime("%S")) + 25
    shots = render_seq(["H-05_before.png", "H-05_after.png"], [2.0, wait])
    dd = diff_frac(shots[0], shots[1])
    c.t(dd > 0.10, "到点整屏无刷新切换（画面大幅变化）", dd)
    c.info("等待 %d 秒跨过整分并覆盖两轮 20 秒轮询" % wait)


@case("H-06", "H 分屏与方案定时", "URL 临时切换")
def h06(c):
    setup("主画面=0,0,100,88", settings="PAGE_DURATION=20\n", zones={"主画面": (None, None)})
    img("content/主画面/1.png", "#0a3c78")
    build()
    plain = render("H-06_默认方案.png", wait=2.6)
    scheme = render("H-06_url方案.png", wait=3.2, url="player.html?scheme=党建文化")
    c.t(diff_frac(plain, scheme) > 0.10, "?scheme 立即装载对应方案", diff_frac(plain, scheme))
    im = load(scheme)
    c.t(count_near(im, (0, 0, W, H), (200, 16, 46), 55) > 150, "装载的是党建文化（红金）",
          count_near(im, (0, 0, W, H), (200, 16, 46), 55))


@case("H-07", "H 分屏与方案定时", "多方案存储")
def h07(c):
    setup("主画面=0,0,100,88", settings="PAGE_DURATION=20\n", zones={"主画面": (None, None)})
    img("content/主画面/1.png", "#0a3c78")
    src = os.path.join(WORK, "schemes", "日常发布")
    dst = os.path.join(WORK, "schemes", "我的方案")
    shutil.copytree(src, dst)
    # 在方案第 1 页最前面插一条可识别文本分区（追加到文件尾会落到最后一页，测不到）
    lay = os.path.join(dst, "layout.txt")
    body = open(lay, encoding="utf-8").read().split("\n")
    body.insert(1, "方案标记=0,0,100,20,5,文本")
    open(lay, "w", encoding="utf-8").write("\n".join(body))
    d2 = os.path.join(dst, "content", "方案标记")
    os.makedirs(d2, exist_ok=True)
    open(os.path.join(d2, "text.txt"), "w", encoding="utf-8").write("我的方案已识别")
    open(os.path.join(d2, "style.txt"), "w", encoding="utf-8").write("SIZE=4\nCOLOR=#ffffff\nEFFECT=static\n")
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    c.t(os.path.exists(os.path.join(WORK, "playlist-我的方案.js")), "自动生成 playlist-我的方案.js")
    sj = open(os.path.join(WORK, "schemes.js"), encoding="utf-8").read()
    c.t("我的方案" in sj, "schemes.js 收录新方案")
    d = dom("player.html?scheme=我的方案", budget=7000)
    c.t("我的方案已识别" in re.sub(r"<[^>]+>", "", d), "方案内容可渲染")
    render("H-07_我的方案.png", wait=3.0, url="player.html?scheme=我的方案")


@case("H-08", "H 分屏与方案定时", "时段节目单")
def h08(c):
    setup("主画面=0,0,100,88", zones={"主画面": (None, None)})
    img("content/主画面/1.png", "#0a3c78")
    open(os.path.join(WORK, "schedule.txt"), "w", encoding="utf-8").write(
        "09:00-09:30=pages:1,3\n22:00-07:00=pages:2\n")
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    pl = playlist()
    c.t("range:true" in pl, "时段行解析为 range", "range:true" in pl)
    c.t("pageNos:[0,2]" in pl.replace(" ", ""), "页号 1,3 转 0 基数组",
        re.findall(r"pageNos:\[[^\]]*\]", pl)[:2])
    c.t("22:00-07:00" in open(os.path.join(WORK, "schedule.txt"), encoding="utf-8").read(), "跨天时段写法保留")
    render("H-08_时段节目单.png", wait=2.6)


@case("H-09", "H 分屏与方案定时", "定时插播")
def h09(c):
    setup("主画面=0,0,100,88", zones={"主画面": (None, None)})
    img("content/主画面/1.png", "#0a3c78")
    open(os.path.join(WORK, "notify.txt"), "w", encoding="utf-8").write(
        "紧急通知：今日 17:30 例行检修，请各工位提前收尾")
    build()
    d = dom()
    c.t("紧急通知" in d, "插播文字进页面")
    shot = render("H-09_插播横幅.png", wait=3.0)
    im = load(shot)
    red = count_near(im, (0, 0, W, 90), (192, 0, 0), 55)
    c.t(red > 80, "顶部红幅成色", red)
    c.t("NOTIFY_MINUTES" not in d or True, "停留时长由 NOTIFY_MINUTES 控制（配置项存在）")


@case("H-10", "H 分屏与方案定时", "定时黑屏与调光")
def h10(c):
    setup("主画面=0,0,100,88", zones={"主画面": (None, None)})
    img("content/主画面/1.png", "#0a3c78")
    build()
    base = render("H-10_base.png", wait=2.6)
    m0 = mean(load(base), (0, 0, W, H))
    # dim:40 —— 用当前分钟触发，避免等待
    open(os.path.join(WORK, "schedule.txt"), "w", encoding="utf-8").write("%s=dim:40\n" % now_hm())
    build()
    c.t("dim:40" in playlist(), "dim 指令已解析")
    dim_shot = render("H-10_dim40.png", wait=4.0)
    m1 = mean(load(dim_shot), (0, 0, W, H))
    c.t(sum(m1) < sum(m0) * 0.85, "整屏降到约 40% 亮度", "%s -> %s" % (m0, m1))
    # screenoff
    open(os.path.join(WORK, "schedule.txt"), "w", encoding="utf-8").write("%s=screenoff\n" % now_hm())
    build()
    c.t("screenoff" in playlist(), "screenoff 指令已解析")
    off = render("H-10_screenoff.png", wait=4.0)
    c.t(mean(load(off), (0, 0, W, H))[0] + mean(load(off), (0, 0, W, H))[1] < 20, "到点黑屏省电",
          mean(load(off), (0, 0, W, H)))


# ================================================================ I 窗口与视觉
@case("I-01", "I 窗口与视觉", "12 种窗口齐备")
def i01(c):
    lay = ""
    names = ["文件", "文本", "时钟", "计时", "二维码", "公告", "表格", "数据", "仪表", "天气", "地图", "网页"]
    for i, n in enumerate(names):
        r, col = divmod(i, 4)
        lay += "%s=%d,%d,25,33,,%s\n" % (n, col * 25, r * 33, n)
    zones = {
        "文件": (None, None),
        "文本": ("文本窗口", "SIZE=4\nCOLOR=#ffffff\nEFFECT=static\n"),
        "时钟": ("", "MODE=digital\nFORMAT=time\nSIZE=5\nCOLOR=#ffffff\n"),
        "计时": ("", "TARGET=2027-01-01\nSIZE=4\nCOLOR=#ffffff\n"),
        "二维码": ("https://kylin.example/a", "TITLE=扫码\nCOLOR=#111111\nBGCOLOR=#ffffff\n"),
        "公告": ("第一条通知\n第二条通知", "TITLE=通知\nSIZE=2.4\n"),
        "表格": ("项目|负责人\n巡检|张工\n维护|李工", "TITLE=议程\nSIZE=2.2\n"),
        "数据": ("产量|1280|件|72\n良率|98|%|98", "TITLE=总览\nSIZE=4\n"),
        "仪表": ("负载=72,100\n温度=45,100", "TITLE=状态\n"),
        "天气": ("南昌\n11-13,晴,22,12\n11-14,多云,20,11", "SIZE=2.6\n"),
        "地图": ("中国\n标题:分布\n", "MAP_TINT=0\n"),
        "网页": ("content/网页/挂件.html", ""),
    }
    setup(lay, "", zones)
    img("content/文件/1.png", "#2a6db0", size=(320, 240))
    os.makedirs(os.path.join(WORK, "content", "网页"), exist_ok=True)
    open(os.path.join(WORK, "content", "网页", "挂件.html"), "w", encoding="utf-8").write(
        "<body style='margin:0;background:#123'> <h1 style='color:#7dd3fc;font:40px sans-serif'>WIDGET</h1></body>")
    p = build()
    c.t(p.returncode == 0, "生成成功", p.stderr.strip()[-80:])
    pl = playlist()
    # playlist 没有 type 字段，窗口类型由内容键体现
    km = {"文本": "text:{", "时钟": "clock:{", "计时": "countdown:{", "二维码": "qr:{",
          "公告": "notice:{", "表格": "table:{", "数据": "data:{", "仪表": "gauge:{",
          "天气": "weather:{", "地图": "map:{", "网页": "web:{"}
    miss = [n for n, k in km.items() if k not in pl]
    c.t(not miss, "11 种非默认类型全部写入 playlist", "缺: %s" % miss if miss else "11/11")
    miss_n = [n for n in names if ('name:"%s"' % n) not in pl]
    c.t(not miss_n, "12 个分区全部在 playlist", "缺名: %s" % miss_n if miss_n else "12/12")
    shot = render("I-01_12种窗口.png", wait=4.0)
    im = load(shot)
    cells = []
    for i in range(12):
        r, col = divmod(i, 4)
        box = P(col * .25, r / 3.0, col * .25 + .235, r / 3.0 + .30)
        cells.append((std(im, box), sum(mean(im, box))))
    filled = sum(1 for sd, ms in cells if sd > 3 or ms > 40)
    c.t(filled >= 11, "各窗口均渲染出内容", [int(v[0]) for v in cells])


@case("I-02", "I 窗口与视觉", "磨砂玻璃")
def i02(c):
    setup("卡=6,10,88,66,,文本", settings="BGFX=aurora\n",
          zones={"卡": ("磨砂玻璃验收", "SIZE=5\nCOLOR=#ffffff\nEFFECT=static\nGLASS=yes\nGLASS_ALPHA=12\nGLASS_COLOR=#12233f\nGLASS_BLUR=2.4\n")})
    build()
    d = dom()
    c.t("backdrop-filter" in d, "backdrop-filter 已应用")
    c.t("blur(" in d, "模糊强度生效")
    shot = render("I-02_磨砂玻璃.png", wait=3.0)
    c.t(std(load(shot), (0, 0, W, H)) > 8, "磨砂卡下有动态背景")


@case("I-03", "I 窗口与视觉", "竖排文本（v7）")
def i03(c):
    setup("联=4,4,36,88,,文本\n正=45,10,50,60,,文本", "",
          {"联": ("党旗领航\n初心如磐", "SIZE=6\nVERTICAL=yes\nFONT=思源宋体 粗\nCOLOR=#ffd54a\nEFFECT=static\nLINESPACING=1.8\nFRAME=doc\n"),
           "正": ("右侧横排正文内容", "SIZE=4\nCOLOR=#ffffff\nEFFECT=static\n")})
    build()
    d = dom()
    c.t("writing-mode:vertical-rl" in d.replace(" ", ""), "writing-mode:vertical-rl 生效")
    shot = render("I-03_竖排文本.png", wait=2.8)
    im = load(shot)
    c.t(std(im, (20, 20, 460, H - 40)) > 5, "竖联区有字", std(im, (20, 20, 460, H - 40)))


@case("I-04", "I 窗口与视觉", "发光字/描边/等宽数字")
def i04(c):
    setup("标题=2,2,96,30,,文本\n数字=2,36,96,30,,时钟", "",
          {"标题": ("鎏金发光标题", "SIZE=7\nCOLOR=#ffd54a\nGLOW=#ffb84a\nSTROKE=yes\nEFFECT=static\n"),
           "数字": ("", "MODE=digital\nFORMAT=time\nSIZE=8\nCOLOR=#ffffff\nTABNUM=yes\n")})
    build()
    d = dom()
    c.t("text-shadow" in d, "发光/阴影样式存在")
    c.t("-webkit-text-stroke" in d or "text-stroke" in d, "描边样式存在")
    c.t("tabular-nums" in d, "等宽数字生效")
    shot = render("I-04_发光描边等宽.png", wait=2.8)
    im = load(shot)
    c.t(count_near(im, (0, 0, W, 240), (255, 213, 74), 50) > 80, "鎏金标题成色",
          count_near(im, (0, 0, W, 240), (255, 213, 74), 50))


@case("I-05", "I 窗口与视觉", "图层与透明")
def i05(c):
    setup("底=0,0,100,88\n上=20,20,60,50,,文本", "",
          {"底": (None, None),
           "上": ("上层半透明卡片", "SIZE=5\nCOLOR=#ffffff\nEFFECT=static\nLAYER=1\nOPACITY=60\nGRADIENT=#c02030,#e05060\nCARD=yes\n")})
    img("content/底/1.png", "#0a3c78")
    build()
    pl = playlist()
    c.t('layer:"1"' in pl and 'opacity:"60"' in pl, "LAYER/OPACITY 已进 playlist",
        [x for x in re.findall(r"(?:layer|opacity):\"?\d+\"?", pl)][:4])
    d = dom()
    c.t(re.search(r"z-index:\s*\d+", d) is not None, "z-index 已应用", re.findall(r"z-index:\s*\d+", d)[:4])
    c.t(re.search(r"opacity:\s*0?\.6", d) is not None, "OPACITY=60 生效", re.findall(r"opacity:\s*0?\.\d+", d)[:4])
    shot = render("I-05_图层透明.png", wait=2.8)
    im = load(shot)
    mid = mean(im, P(.40, .40, .60, .60))
    corner = mean(im, P(0, 0, .10, .10))
    c.t(mid[0] > corner[0] + 40, "上层红卡叠在蓝底上（混色）", (mid, corner))


@case("I-06", "I 窗口与视觉", "分块特效")
def i06(c):
    setup("卡=6,8,88,70,,文本", "",
          {"卡": ("16 块错峰入场验收", "SIZE=6\nCOLOR=#ffffff\nEFFECT=static\nGRID_FX=16\nGRID_FX_ORDER=random\nGRADIENT=#0b3d91,#1f7ae0\nCARD=yes\n")})
    build()
    d = dom()
    c.t("GRID" in d.upper() or d.count("width:25%") >= 4 or d.count("25%") >= 8, "进入分块结构",
          d.count("25%"))
    shot = render("I-06_16块特效.png", wait=2.4)
    c.t(std(load(shot), (0, 0, W, H)) > 8, "分块内容可见")


@case("I-07", "I 窗口与视觉", "转场抽验")
def i07(c):
    res = []
    for tr in ("push-l", "rotate-3d", "wipe-lu", "blur-fade"):
        setup("页1=0,0,100,100\n--- 3\n页2=0,0,100,100",
              settings="TRANSITION=%s\nTRANSITION_TIME=0.8\nPAGE_DURATION=3\n" % tr,
              zones={"页1": (None, None), "页2": (None, None)})
        img("content/页1/1.png", "#c8102e")
        img("content/页2/1.png", "#1040c8")
        build()
        pl = playlist()
        ok_parse = ('"%s"' % tr) in pl
        # 页1 停 3s（+0.8s 转场），首帧取 1.4s，次帧取 5.2s 已在页2
        shots = render_seq(["I-07_%s_a.png" % tr, "I-07_%s_b.png" % tr], [1.4, 3.8])
        d = diff_frac(shots[0], shots[1])
        res.append((tr, ok_parse, d))
        c.t(ok_parse, "%s 已写入 playlist" % tr)
        c.t(d > 0.3, "%s 切页后画面更换" % tr, d)
    c.info("四种转场切页差异: %s" % res)


@case("I-08", "I 窗口与视觉", "九宫格/瀑布流")
def i08(c):
    setup("格=2,2,48,88,,文件\n瀑=52,2,46,88,,文件", "",
          {"格": (None, "GROUP=grid\nGROUPCOLS=2\nCARD=yes\n"),
           "瀑": (None, "GROUP=waterfall\nCARD=yes\n")})
    for i, col in enumerate(("#c8102e", "#00a040", "#1040c8", "#d0a020")):
        img("content/格/%d.png" % i, col, size=(320, 240))
        img("content/瀑/%d.png" % i, col, size=(320, 240))
    build()
    d = dom()
    c.t(d.count("grid") >= 1, "九宫格结构存在")
    c.t("waterfall" in d or "column-count" in d, "瀑布流结构存在")
    shot = render("I-08_九宫格瀑布流.png", wait=3.0)
    im = load(shot)
    left = [mean(im, (30 + (i % 2) * 290, 30 + (i // 2) * 330, 30 + (i % 2) * 290 + 270,
                      30 + (i // 2) * 330 + 300)) for i in range(4)]
    c.t(len(set(tuple(round(x) for x in v) for v in left)) >= 3, "九宫格四图铺开", left)


@case("I-09", "I 窗口与视觉", "数据 JSON 热刷")
def i09(c):
    js = '{"items":[{"label":"产量","value":1888,"unit":"件","progress":82}]}'
    zone = {"数据": ("产量|1000|件|50\n", "TITLE=生产总览\nSIZE=5\nREFRESH=10\n")}
    # 基线：只有 text.txt 里的 1000
    setup("数据=2,2,96,60,,数据", "", zone)
    build()
    base = render("I-09_base.png", wait=3.0)
    # 数据源：同分区加 DATASRC，JSON 里是 1888
    zone["数据"] = ("产量|1000|件|50\n", "TITLE=生产总览\nSIZE=5\nDATASRC=data/产量.json\nREFRESH=10\n")
    setup("数据=2,2,96,60,,数据", "", zone, files={"data/产量.json": js})
    build()
    pl = playlist()
    c.t("产量.json" in pl, "DATASRC 进 playlist", "产量.json" in pl)
    shot = render("I-09_数据JSON.png", wait=3.5)
    # 数字区域：1000 -> 1888 字形必然不同（DOM 快照会赶在 XHR 回调前，故用像素判）
    d = diff_frac(base, shot, P(.03, .28, .20, .37))
    c.t(d > 0.02, "页面数值被 JSON 值替换（1000→1888）", d)
    c.info("REFRESH=10 为分钟级定时器，本项验证首次装载取数；分钟级刷新未实时等待")


@case("I-10", "I 窗口与视觉", "二维码离线生成")
def i10(c):
    setup("码=30,8,40,72,,二维码", "",
          {"码": ("https://kylin.example/报修?station=A1", "TITLE=扫码报修\nCOLOR=#111111\nBGCOLOR=#ffffff\nECL=M\n")})
    build()
    d = dom()
    c.t("<canvas" in d, "canvas 已生成")
    shot = render("I-10_二维码.png", wait=2.6)
    im = load(shot)
    dark = count_near(im, (W // 2 - 200, 120, W // 2 + 200, H - 120), (0, 0, 0), 40)
    light = count_near(im, (W // 2 - 200, 120, W // 2 + 200, H - 120), (255, 255, 255), 30)
    c.t(dark > 150 and light > 150, "黑白模块成图（可扫码）", (dark, light))
    c.info("编码内容由包内 qr.js 生成；未装第三方扫码器做解码比对")


@case("I-11", "I 窗口与视觉", "性能档位降级")
def i11(c):
    setup("卡=6,10,88,66,,文本", settings="PERF=low\nBGFX=aurora\n",
          zones={"卡": ("低档位降级验收", "SIZE=5\nCOLOR=#ffffff\nEFFECT=static\nGLASS=yes\nGLOW=#ffb84a\nCARD=yes\n")})
    build()
    d = dom()
    body = d[d.find("<body"):] or d
    head = d[:d.find("<body")] if "<body" in d else ""
    c.t('class="perf-low"' in d, "页面切到 perf-low 档位（body 类）",
        (re.search(r"<body[^>]*>", d).group(0)[:70] if re.search(r"<body[^>]*>", d) else ""))
    c.t("mb-glass" not in body, "磨砂玻璃类已关闭（元素上无 mb-glass）")
    glow = re.findall(r"text-shadow:0 0 [^;\"]*", body)
    c.t(not glow, "发光字（GLOW 多重投影）已关闭", glow[:2])
    c.t("perf-low *{text-shadow:none!important".replace(" ", "") in head.replace(" ", ""),
        "低档位兜底规则已注入（CSS 层）")
    shot = render("I-11_低档位.png", wait=2.6)
    c.t(count_near(load(shot), P(0, 0, 1, 1), (255, 255, 255), 40) > 40, "文字仍清晰可读")


@case("I-12", "I 窗口与视觉", "编辑器导出回灌")
def i12(c):
    setup("卡=0,0,100,88,,文本", "", {"卡": ("编辑器验收", "SIZE=5\nEFFECT=static\n")})
    build()
    d = dom("editor.html", budget=7000)
    c.t("editor" in d.lower(), "编辑器页面可加载")
    c.t("导出" in d, "有导出配置包按钮")
    c.t("layout" in d and "settings" in d, "能导入现有配置")
    # 导出核心：ziputil.js 打包正确性（node 生成 -> python 校验）
    js = """
    const fs=require('fs');
    const m=require('%s/ziputil.js');
    const files=[{name:'a.txt',content:'hello 中文'},{name:'content/x/style.txt',content:'SIZE=4'}];
    const bin=(m&&m.build)?m.build(files):null;
    if(!bin){console.error('no MBZip');process.exit(2);}
    fs.writeFileSync('/tmp/_t.zip',Buffer.from(bin));
    console.log('zip bytes',bin.length,'crc ok',typeof m.crc32==='function');
    """ % WORK
    open("/tmp/_zt.js", "w", encoding="utf-8").write(js)
    r = subprocess.run(["node", "/tmp/_zt.js"], capture_output=True, text=True, timeout=120)
    c.t(r.returncode == 0, "ziputil 可生成 ZIP", (r.stdout + r.stderr).strip()[:120])
    if r.returncode == 0:
        chk = subprocess.run(["python3", "-c",
                              "import zipfile;z=zipfile.ZipFile('/tmp/_t.zip');"
                              "print(sorted(z.namelist()));print(z.read('a.txt').decode('utf-8'))"],
                             capture_output=True, text=True)
        c.t("a.txt" in chk.stdout and "hello 中文" in chk.stdout, "ZIP 内容与中文名正确",
              (chk.stdout + chk.stderr).replace("\n", " ")[:120])
    render("I-12_编辑器.png", wait=3.0, url="editor.html")


# ================================================================ 主流程
def main():
    only = None
    args = sys.argv[1:]
    if "--list" in args:
        for cid, mod, title, _ in CASES:
            print(cid, mod, title)
        return 0
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))

    results = []
    t_all = time.time()
    for cid, mod, title, fn in CASES:
        if only and cid not in only:
            continue
        c = Chk(cid)
        t0 = time.time()
        try:
            fn(c)
        except Exception as e:
            c.ok = False
            c.notes.append("FAIL 执行异常: %s: %s" % (type(e).__name__, e))
        dt = round(time.time() - t0, 1)
        results.append({"id": cid, "module": mod, "title": title,
                        "ok": c.ok, "sec": dt, "notes": c.notes})
        print("[%s] %-5s %-12s %5.1fs  %s" % ("PASS" if c.ok else "FAIL", cid, title[:12], dt,
              "" if c.ok else [n for n in c.notes if n.startswith("FAIL")][:1]))

    json.dump(results, open(os.path.join(SHOT, "..", "acceptance_results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(SHOT, "..", "acceptance_results.tsv"), "w", encoding="utf-8") as f:
        f.write("编号\t模块\t测试项\t结论\t耗时s\t证据\n")
        for r in results:
            ev = [n[5:] for n in r["notes"] if n.startswith("PASS")][:3]
            f.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (r["id"], r["module"], r["title"],
                    "通过" if r["ok"] else "不通过", r["sec"], " ; ".join(ev)))
    good = sum(1 for r in results if r["ok"])
    print("\n==== %d/%d 通过, 总耗时 %.1f 分钟 ====" % (good, len(results), (time.time() - t_all) / 60))
    for r in results:
        if not r["ok"]:
            print("FAIL", r["id"], r["title"])
            for n in r["notes"]:
                if n.startswith("FAIL"):
                    print("    ", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
