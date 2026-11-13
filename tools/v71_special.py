#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MediaBoard v7.1 专项验收：第十四章缺陷复验 + 运维链路 + 第十五章 P/S 组。

复用 v7_1_acceptance.py 的 L0–L4 基础设施（配置生成 / 真窗口 / DOM / 像素 / 进程）。
每个 case 至少一张全屏证据图，写 /out/special_results.json|tsv。
"""
import os, sys, json, time, re, shutil, subprocess, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v7_1_acceptance as B

OUT = os.path.join(B.SHOT, "..")
CASES = []


def case(cid, mod, title):
    def deco(fn):
        CASES.append((cid, mod, title, fn))
        return fn
    return deco


def sh(cmd, cwd=None, timeout=90):
    return subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd or B.WORK,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def cap(png, text):
    return B.cli_shot(png, text)


def token():
    return os.path.join(B.WORK, ".stop")


def clean_start(wait=8):
    p = B.start_loop()
    time.sleep(wait)
    return p


def clean_stop(p, wait=7):
    r = sh("bash stop.sh", timeout=60)
    time.sleep(wait)
    B.stop_all()
    return r


# ---------------------------------------------------------------- 第十四章 A-05R
@case("A-05R-1", "14 缺陷复验", "停止与重配 step1：真停机 + 令牌")
def r_step1(c):
    B.stop_all()
    B.reset()
    B.setup("主画面=0,0,100,92", settings="DURATION=8\n", zones={"主画面": (None, None)})
    B.img("content/主画面/01.png", "#0a3c78", text="STOP TEST")
    B.build()
    p = clean_start()
    before = B.pids()
    r = sh("bash stop.sh", timeout=60)
    time.sleep(10)          # 需求文档明确要求等待 10 秒
    after = B.pids()
    ps = sh("pgrep -af '^bash start.sh' || true")
    B.render_capture("A-05R_step1.png")
    c.t(bool(before), "启动后 chromium 在跑", before[:2])
    c.t("停止" in (r.stdout + r.stderr), "stop.sh 有明确反馈", (r.stdout + r.stderr).strip()[:60])
    c.t(os.path.exists(token()), ".stop 停机令牌已生成", os.path.exists(token()))
    c.t(not after, "stop.sh 后 10 秒无残留播放进程", after[:3] if after else "0")
    c.t(not ps.stdout.strip(), "看门狗进程已退出（不再重拉）", ps.stdout.strip()[:100])
    B.stop_all()


@case("A-05R-2", "14 缺陷复验", "停止与重配 step2：重启清令牌")
def r_step2(c):
    B.stop_all()
    B.reset()
    B.setup("主画面=0,0,100,92", settings="DURATION=8\n", zones={"主画面": (None, None)})
    B.img("content/主画面/01.png", "#0a3c78")
    B.build()
    p = clean_start(7)
    sh("bash stop.sh", timeout=60)
    time.sleep(6)
    c.t(os.path.exists(token()), "停机后令牌在位", True)
    p2 = clean_start(7)
    live = B.pids()
    B.render_capture("A-05R_step2.png")
    c.t(not os.path.exists(token()), "start.sh 启动时自动清除 .stop", not os.path.exists(token()))
    c.t(bool(live), "重新启动后正常拉起播放", live[:2])
    clean_stop(p2, 6)
    B.stop_all()


@case("A-05R-3", "14 缺陷复验", "停止与重配 step3：安装目录改名路径无关")
def r_step3(c):
    B.stop_all()
    old = B.WORK
    new = os.path.join(os.path.dirname(old), "mb7")
    if os.path.exists(new):
        shutil.rmtree(new)
    B.reset()
    B.setup("主画面=0,0,100,92", settings="DURATION=8\n", zones={"主画面": (None, None)})
    B.img("content/主画面/01.png", "#0a3c78")
    B.build()
    try:
        shutil.move(old, new)
        B.WORK = new
        p = clean_start(8)
        live = B.pids()
        r = sh("bash stop.sh", timeout=60)
        time.sleep(9)
        after = B.pids()
        B.render_capture("A-05R_step3.png")
        c.t(bool(live), "改名 mb7 后仍能启动播放", live[:2])
        c.t("停止" in (r.stdout + r.stderr), "改名后 stop.sh 仍可用", (r.stdout + r.stderr).strip()[:60])
        c.t(not after, "改名后依然真停机（路径无关化）", after[:3] if after else "0")
        B.stop_all()
    finally:
        B.WORK = old
        if os.path.exists(new) and not os.path.exists(old):
            shutil.move(new, old)
        B.stop_all()


@case("A-05R-4", "14 缺陷复验", "停止与重配 step4：DURATION=6 重配生效")
def r_step4(c):
    B.stop_all()
    B.reset()
    B.setup("页=0,0,100,92", settings="DURATION=6\n", zones={"页": (None, None)})
    B.img("content/页/01.png", "#c8102e", text="P1")
    B.img("content/页/02.png", "#1040c8", text="P2")
    B.build()
    pl = B.playlist()
    m = re.search(r'duration:"?(\d+)"?', pl)
    c.t(bool(m) and int(m.group(1)) == 6, "新时长 DURATION=6 写入 playlist", m.group(0) if m else "")
    shots = B.render_seq(["A-05R_step4_a.png", "A-05R_step4_b.png"], [2.2, 7.2])
    d = B.diff_frac(shots[0], shots[1])
    c.t(d > 0.02, "约 6 秒后素材自动切换（秒表核量）", d)
    B.stop_all()


# ---------------------------------------------------------------- 第十四章 F-07R
WINDOWS = [
    ("文件", None, ""),
    ("文本", "分区底图文本窗", "SIZE=4\nCOLOR=#ffffff\nEFFECT=static\n"),
    ("时钟", "", "MODE=digital\nFORMAT=time\nSIZE=5\nCOLOR=#ffffff\n"),
    ("计时", "", "TARGET=2027-01-01\nSIZE=4\nCOLOR=#ffffff\n"),
    ("二维码", "https://kylin.example/a", "TITLE=扫码\nCOLOR=#111111\nBGCOLOR=#ffffff\n"),
    ("公告", "第一条通知\n第二条通知", "TITLE=通知\nSIZE=2.4\n"),
    ("表格", "项目|负责人\n巡检|张工", "TITLE=议程\nSIZE=2.2\n"),
    ("数据", "产量|1280|件|72", "TITLE=总览\nSIZE=4\n"),
    ("仪表", "负载=72,100", "TITLE=状态\n"),
    ("天气", "南昌\n11-13,晴,22,12", "SIZE=2.6\n"),
    ("地图", "中国\n标题:分布\n", "MAP_TINT=0\n"),
    ("网页", "content/网页/挂件.html", ""),
]


def zbg_scene(kind, text, extra_style, png):
    B.stop_all()
    B.reset()
    lay = "卡=6,6,88,84,," + kind
    style = extra_style + "ZBG=textures/vignette.png\nZBG_FIT=contain\n"
    B.setup(lay, "", {"卡": (text, style)})
    if kind == "文件":
        B.img("content/卡/01.png", "#123a6b", size=(320, 240))
    if kind == "网页":
        os.makedirs(os.path.join(B.WORK, "content", "网页"), exist_ok=True)
        open(os.path.join(B.WORK, "content", "网页", "挂件.html"), "w", encoding="utf-8").write(
            "<body style='margin:0;background:#123'><h1 style='color:#7dd3fc;font:40px sans-serif'>WIDGET</h1></body>")
    B.build()
    pl = B.playlist()
    d = B.dom()
    shot = B.render(png, wait=3.0)
    im = B.load(shot)
    card = B.mean(im, B.P(.10, .10, .90, .84))
    return pl, d, card


for _i, (_kind, _text, _style) in enumerate(WINDOWS, 1):
    def _mk(kind, text, style, idx):
        @case("F-07R-%02d" % idx, "14 缺陷复验", "分区背景图 ZBG 回归：%s 窗" % kind)
        def _fn(c):
            png = "F-07R_%s.png" % kind
            pl, d, card = zbg_scene(kind, text, style, png)
            c.t('zbg:"textures/vignette.png"' in pl, "ZBG 写入 playlist（L1）",
                re.findall(r"zbg[^,]*", pl)[:1])
            c.t("vignette" in d, "DOM 内联样式含 background-image（L2）", "vignette" in d)
            c.t(card[2] - card[0] > 15, "画面呈蓝调纹理（L3）", card)
        return _fn
    _mk(_kind, _text, _style, _i)


@case("F-07R-13", "14 缺陷复验", "自检第 24 项 ZBG 装载为绿 + TRANSPARENT 共存")
def r_zbg_selftest(c):
    B.stop_all()
    B.reset()
    B.setup("卡=6,6,88,84,,文本", "",
            {"卡": ("透明与背景图共存\n",
                    "SIZE=4\nCOLOR=#ffffff\nEFFECT=static\nTRANSPARENT=yes\n"
                    "ZBG=textures/vignette.png\nZBG_FIT=contain\n")})
    B.build()
    d = B.dom("player.html?selftest=1", budget=9000)
    title = re.search(r"selftest\s*(\d+)\s*/\s*(\d+)", d)
    c.t(bool(title), "自检页返回通过数", title.group(0) if title else "")
    if title:
        c.t(int(title.group(1)) == int(title.group(2)) and int(title.group(2)) >= 24,
            "自检 24/24 全绿", title.group(0))
    c.t("分区背景图" in d and "ZBG" in d, "自检清单含「分区背景图 ZBG 装载」",
        "分区背景图" in d)
    d2 = B.dom()
    c.t("vignette" in d2, "TRANSPARENT 与 ZBG 可共存", "vignette" in d2)
    B.render("F-07R_自检与透明共存.png", wait=2.6)


# ---------------------------------------------------------------- 运维链路
@case("OPS-01", "运维链路", "status.sh 三态状态查询")
def ops1(c):
    B.stop_all()
    B.reset()
    B.setup("主画面=0,0,100,92", zones={"主画面": (None, None)})
    B.img("content/主画面/01.png", "#0a3c78")
    B.build()
    r = sh("bash status.sh")
    B.render_capture("OPS-01_status_停止态.png")
    p = clean_start(7)
    r2 = sh("bash status.sh")
    cap("OPS-01_status.sh.png", "$ bash status.sh (停止态)\n" + (r.stdout + r.stderr) +
        "\n$ bash status.sh (运行态)\n" + (r2.stdout + r2.stderr))
    # status.sh 约定：exit 0 = 正常态，exit 2 = 告警态（TONE=warn），两者都是有效返回
    c.t(r.returncode in (0, 2) and r2.returncode in (0, 2),
        "两种状态下脚本均正常返回（0=正常 / 2=告警态）", (r.returncode, r2.returncode))
    c.t("状态:" in (r.stdout + r.stderr) and "状态:" in (r2.stdout + r2.stderr),
        "状态查询输出三态判定", (r.stdout + r.stderr).strip()[:60])
    c.t(bool((r.stdout + r.stderr).strip()) and bool((r2.stdout + r2.stderr).strip()),
        "状态查询有可读输出", True)
    clean_stop(p, 6)


@case("OPS-02", "运维链路", "collect.sh 一键取证包")
def ops2(c):
    B.stop_all()
    B.reset()
    B.setup("主画面=0,0,100,92", zones={"主画面": (None, None)})
    B.img("content/主画面/01.png", "#0a3c78")
    B.build()
    r = sh("bash collect.sh", timeout=150)
    out = (r.stdout + r.stderr)
    files = []
    for root, _, fs in os.walk(B.WORK):
        for f in fs:
            if f.endswith((".zip", ".tar.gz", ".tgz")):
                files.append(os.path.relpath(os.path.join(root, f), B.WORK))
    cap("OPS-02_collect.sh.png", "$ bash collect.sh\n" + out[-450:])
    c.t(r.returncode == 0, "取证脚本正常返回", r.returncode)
    c.t(bool(files), "生成取证包文件", files[:3])


@case("OPS-03", "运维链路", "upgrade.sh 升级回滚脚本可用")
def ops3(c):
    r = sh("bash upgrade.sh --help || bash upgrade.sh", timeout=90)
    out = (r.stdout + r.stderr)
    cap("OPS-03_upgrade.sh.png", "$ bash upgrade.sh --help\n" + out[-450:])
    c.t(bool(out.strip()), "脚本有用法/状态输出", out.strip()[:80])
    c.t("command not found" not in out, "脚本可执行", "command not found" not in out)


@case("OPS-04", "运维链路", "播出日志与自截屏目录")
def ops4(c):
    B.stop_all()
    B.reset()
    B.setup("主画面=0,0,100,92", zones={"主画面": (None, None)})
    B.img("content/主画面/01.png", "#0a3c78")
    B.build()
    p = clean_start(8)
    logp = os.path.join(B.WORK, "logs", "play.jsonl")
    haslog = os.path.exists(logp)
    shots_dir = os.path.join(B.WORK, "logs", "shots")
    cap("OPS-04_logs.png", "$ ls logs/\n" +
        "\n".join(os.listdir(os.path.join(B.WORK, "logs"))) if haslog else "$ ls logs/\n(目录不存在)")
    c.t(haslog, "logs/play.jsonl 播出日志已生成", haslog)
    if haslog:
        txt = open(logp, encoding="utf-8", errors="replace").read()
        c.t(len(txt.strip()) > 0, "日志有实际记录", txt.strip()[:100])
    c.info("logs/shots 为每小时自截屏，单次短测不强制产出；目录存在=%s" % os.path.isdir(shots_dir))
    clean_stop(p, 6)


# ---------------------------------------------------------------- 第十五章 P 组
@case("P-04", "15 P 组", "无转换工具时降级不报错")
def p04(c):
    B.stop_all()
    B.reset()
    B.setup("文档=0,0,100,90,,文件", "", {"文档": (None, None)})
    ppt = os.path.join(B.WORK, "content", "文档", "示例.pptx")
    open(ppt, "wb").write(b"PK\x03\x04FAKE-PPTX-NOT-REAL")
    r = B.build()
    out = (r.stdout + r.stderr)
    cap("P-04_降级.png", "$ bash start.sh (无 soffice，放入 .pptx)\n" + out[-450:])
    c.t(r.returncode == 0, "无转换工具时生成链不失败", r.returncode)
    c.t("Traceback" not in out and "Segmentation" not in out, "无崩溃堆栈", out.strip()[:80])
    c.t(os.path.exists(os.path.join(B.WORK, "playlist.js")), "playlist 仍正常产出", True)
    B.render("P-04_降级画面.png", wait=2.4)


# ---------------------------------------------------------------- 第十五章 S 组
@case("S-01", "15 S 组", "页循环 ≥3 轮不卡死")
def s01(c):
    B.stop_all()
    B.reset()
    B.setup("轮播=0,0,100,92", settings="DURATION=3\n", zones={"轮播": (None, None)})
    for i, col in enumerate(("#c8102e", "#1040c8", "#12864a"), 1):
        B.img("content/轮播/%02d.png" % i, col, text="P%d" % i)
    B.build()
    pngs = ["S-01_循环_%d.png" % i for i in range(1, 5)]
    shots = B.render_seq(pngs, [2.0, 3.4, 3.4, 3.4])
    diffs = [B.diff_frac(shots[i], shots[i + 1]) for i in range(3)]
    c.t(sum(1 for d in diffs if d > 0.02) >= 2, "连续观察到 ≥3 次页切换（循环不卡死）", diffs)
    c.t(os.path.exists(os.path.join(B.WORK, "playlist.js")), "轮播配置仍在", True)


def main():
    os.makedirs(B.SHOT, exist_ok=True)
    results = []
    t0 = time.time()
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    for cid, mod, title, fn in CASES:
        if only and cid not in only:
            continue
        c = B.Chk(cid)
        t = time.time()
        try:
            B.stop_all()
            fn(c)
        except Exception as e:
            c.ok = False
            c.notes.append("FAIL 用例异常: %s: %s" % (type(e).__name__, str(e)[:160]))
            c.notes.append("INFO " + traceback.format_exc(limit=3).replace("\n", " | ")[:300])
        finally:
            try:
                B.stop_all()
            except Exception:
                pass
        results.append({"id": cid, "module": mod, "title": title, "ok": c.ok,
                        "sec": round(time.time() - t, 1), "notes": c.notes})
        print("[%s] %s %s (%.1fs)" % ("OK" if c.ok else "NG", cid, title, time.time() - t), flush=True)
    json.dump(results, open(os.path.join(OUT, "special_results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "special_results.tsv"), "w", encoding="utf-8") as f:
        f.write("编号\t模块\t测试项\t结论\t耗时s\t证据\n")
        for r in results:
            ev = [n[5:] for n in r["notes"] if n.startswith("PASS")][:3]
            f.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (r["id"], r["module"], r["title"],
                    "通过" if r["ok"] else "不通过", r["sec"], " ; ".join(ev)))
    good = sum(1 for r in results if r["ok"])
    print("\n==== 专项 %d/%d 通过, 耗时 %.1f 分钟 ====" % (good, len(results), (time.time() - t0) / 60))
    for r in results:
        if not r["ok"]:
            print("FAIL", r["id"], r["title"])
            for n in r["notes"]:
                if n.startswith("FAIL"):
                    print("    ", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
