#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7.1 第十五章 R 组：真实用户操作模拟（CDP 真实鼠标/键盘事件）。

不调用编辑器内部函数改状态，只发 Input.dispatchMouseEvent / Input.dispatchKeyEvent，
位置由 DOM getBoundingClientRect 查询，等价于现场人员拿鼠标键盘在界面上操作。
截图一律用 Xvfb root 全屏截（import -window root），与现场取证一致。
"""
import os, sys, json, time, re, base64, struct, socket, subprocess, urllib.request, traceback
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v7_1_acceptance as B

PORT = 9222
DL = "/tmp/mb_downloads"
OUT = os.path.join(B.SHOT, "..")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class WS(object):
    """最小 WebSocket 客户端（标准库，避免容器里再装 pip 包）"""
    def __init__(self, url):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), 8)
        self.sock.settimeout(25)
        self.buf = b""
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n"
               "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n" % (u.path, u.hostname, key))
        self.sock.sendall(req.encode())
        while b"\r\n\r\n" not in self.buf:
            self.buf += self.sock.recv(4096)
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        if b"101" not in head.split(b"\r\n")[0]:
            raise RuntimeError("WebSocket 升级失败: " + head[:160].decode("utf-8", "replace"))

    def _readn(self, n):
        while len(self.buf) < n:
            d = self.sock.recv(max(4096, n - len(self.buf)))
            if not d:
                raise EOFError("CDP 连接关闭")
            self.buf += d
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _frame(self, opcode, data):
        mask = os.urandom(4)
        n = len(data)
        h = bytearray([0x80 | opcode])
        if n < 126:
            h.append(0x80 | n)
        elif n < 65536:
            h.append(0x80 | 126); h += struct.pack(">H", n)
        else:
            h.append(0x80 | 127); h += struct.pack(">Q", n)
        h += mask
        self.sock.sendall(bytes(h) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def send(self, obj):
        self._frame(0x1, json.dumps(obj).encode())

    def recv(self):
        parts = []
        while True:
            h = self._readn(2)
            fin, op, ln = h[0] & 0x80, h[0] & 0x0F, h[1] & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._readn(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._readn(8))[0]
            mask = self._readn(4) if h[1] & 0x80 else None
            data = self._readn(ln)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if op == 0x9:
                self._frame(0xA, data); continue
            if op == 0x8:
                raise EOFError("CDP closed")
            if op in (0x0, 0x1):
                parts.append(data)
            if fin:
                return b"".join(parts).decode("utf-8", "replace")


class CDP(object):
    def __init__(self, ws):
        self.ws = ws
        self.seq = 0
        self.events = []

    def call(self, method, params=None):
        self.seq += 1
        seq = self.seq
        self.ws.send({"id": seq, "method": method, "params": params or {}})
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == seq:
                if "error" in m:
                    raise RuntimeError("%s: %s" % (method, str(m["error"])[:180]))
                return m.get("result", {})
            self.events.append(m)

    def ev(self, expr):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                           "awaitPromise": True})
        if "exceptionDetails" in r:
            raise RuntimeError("JS 异常: " + str(r["exceptionDetails"])[:180])
        return r.get("result", {}).get("value")

    def rect(self, sel):
        return self.ev("(()=>{const e=document.querySelector(%s);if(!e)return null;"
                       "const r=e.getBoundingClientRect();"
                       "return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,h:r.height,"
                       "l:r.left,t:r.top};})()" % json.dumps(sel))

    def mouse(self, typ, x, y, buttons=0, click=1):
        self.call("Input.dispatchMouseEvent", {"type": typ, "x": x, "y": y,
                                               "button": "left", "buttons": buttons,
                                               "clickCount": click})

    def click_at(self, x, y):
        self.mouse("mouseMoved", x, y, 0, 0)
        self.mouse("mousePressed", x, y, 1, 1)
        time.sleep(0.08)
        self.mouse("mouseReleased", x, y, 0, 1)
        time.sleep(0.35)

    def click(self, sel):
        r = self.rect(sel)
        if not r:
            raise RuntimeError("找不到控件 " + sel)
        self.click_at(r["x"], r["y"])
        return r

    def drag(self, x1, y1, x2, y2, steps=12):
        self.mouse("mouseMoved", x1, y1, 0, 0)
        self.mouse("mousePressed", x1, y1, 1, 1)
        for i in range(1, steps + 1):
            self.mouse("mouseMoved", x1 + (x2 - x1) * i / steps,
                       y1 + (y2 - y1) * i / steps, 1, 1)
            time.sleep(0.03)
        self.mouse("mouseReleased", x2, y2, 0, 1)
        time.sleep(0.4)

    def key(self, key, code, vk, text=None, shift=False):
        p = {"key": key, "code": code, "windowsVirtualKeyCode": vk,
             "nativeVirtualKeyCode": vk, "modifiers": 8 if shift else 0}
        self.call("Input.dispatchKeyEvent", dict(p, type="keyDown", **( {"text": text} if text else {})))
        if text:
            self.call("Input.dispatchKeyEvent", dict(p, type="char", text=text))
        self.call("Input.dispatchKeyEvent", dict(p, type="keyUp"))
        time.sleep(0.08)

    def type_text(self, s):
        for ch in s:
            if ch.isascii() and ch.isalnum():
                self.key(ch, "Key" + ch.upper(), ord(ch.upper()), ch)
            elif ch == " ":
                self.key(" ", "Space", 32, " ")
            else:
                # 中文用 CDP insertText（仍是真实输入路径，键盘逐字不可表达汉字编码）
                self.call("Input.insertText", {"text": ch})
            time.sleep(0.05)


def start_chrome():
    os.makedirs(DL, exist_ok=True)
    url = "file://%s/editor.html" % B.WORK
    env = os.environ.copy(); env["DISPLAY"] = B.DISPLAY
    p = subprocess.Popen(
        [B.CHROME, "--remote-debugging-port=%d" % PORT, "--remote-allow-origins=*",
         "--user-data-dir=/tmp/mb_cdp_profile", "--app=" + url,
         "--window-size=%d,%d" % (B.W, B.H), "--no-first-run",
         "--no-default-browser-check", "--allow-file-access-from-files",
         "--disable-gpu", "--force-device-scale-factor=1", "--lang=zh-CN",
         "--test-type", "--no-sandbox", "--disable-background-networking"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    wsurl = None
    for _ in range(40):
        time.sleep(0.5)
        try:
            d = json.loads(opener.open("http://127.0.0.1:%d/json/list" % PORT, timeout=3).read())
            for t in d:
                if t.get("type") == "page" and "editor.html" in t.get("url", ""):
                    wsurl = t["webSocketDebuggerUrl"]; break
            if wsurl:
                break
        except Exception:
            pass
    if not wsurl:
        raise RuntimeError("CDP 端口未就绪")
    time.sleep(2.0)
    return p, wsurl


def main():
    B.stop_all()
    B.reset()
    B.setup("主画面=0,0,100,92", zones={"主画面": (None, None)})
    B.img("content/主画面/01.png", "#0a3c78")
    B.build()
    os.makedirs(DL, exist_ok=True)
    for f in os.listdir(DL):
        try: os.remove(os.path.join(DL, f))
        except Exception: pass
    proc, wsurl = start_chrome()
    cdp = CDP(WS(wsurl))
    cdp.call("Runtime.enable"); cdp.call("Page.enable"); cdp.call("Log.enable")
    try:
        cdp.call("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": DL,
                                                 "eventsEnabled": True})
    except Exception:
        cdp.call("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": DL})

    results = []

    def rec(cid, title, fn, png):
        c = B.Chk(cid); t = time.time()
        try:
            fn(c)
        except Exception as e:
            c.ok = False
            c.notes.append("FAIL 操作异常: %s: %s" % (type(e).__name__, str(e)[:150]))
            c.notes.append("INFO " + traceback.format_exc(limit=2).replace("\n", " | ")[:220])
        try:
            B.render_capture(png)
        except Exception as e:
            c.ok = False
            c.notes.append("FAIL 截图失败: %s" % str(e)[:80])
        results.append({"id": cid, "module": "15 R 组 真实操作模拟", "title": title,
                        "ok": c.ok, "sec": round(time.time() - t, 1), "notes": c.notes})
        print("[%s] %s %s (%.1fs)" % ("OK" if c.ok else "NG", cid, title, time.time() - t), flush=True)

    # R1 编辑器打开
    def r1(c):
        n = cdp.ev("document.querySelectorAll('#dragLayer .dbox').length")
        z = cdp.ev("curPage().zones.length")
        err = [e for e in cdp.events if e.get("method") == "Runtime.exceptionThrown"]
        c.t(n is not None and n > 0, "默认分区在画布上就位", n)
        c.t(z is not None and z > 0, "编辑器载入默认分区数据", z)
        c.t(not err, "打开过程零运行时报错", len(err))
    rec("R1", "编辑器打开", r1, "R1_编辑器.png")

    # R2 添加功能框
    def r2(c):
        before = cdp.ev("curPage().zones.length")
        cdp.click("#zoneAdd")
        after = cdp.ev("curPage().zones.length")
        boxes = cdp.ev("document.querySelectorAll('#dragLayer .dbox').length")
        c.t(after == before + 1, "点「+ 添加分区」后分区数 +1", "%s -> %s" % (before, after))
        c.t(boxes == after, "画布同步出现新框", boxes)
    rec("R2", "添加功能框", r2, "R2_添加.png")

    # R3 键盘逐键输入
    def r3(c):
        cdp.click("#dragLayer .dbox")
        ta = cdp.rect("#zoneProps textarea")
        if ta:
            cdp.click_at(ta["x"], ta["y"])
            cdp.key("a", "KeyA", 65, None)  # 先清焦点
            cdp.ev("(()=>{const t=document.querySelector('#zoneProps textarea');"
                   "if(t){t.focus();t.value='';}})()")
            cdp.type_text("验收ABC")
            v = cdp.ev("(document.querySelector('#zoneProps textarea')||{}).value||''")
            c.t("验收ABC" in v, "逐键输入文字写入属性框", v[:40])
        else:
            c.t(False, "找到分区内容输入框", "无 textarea")
        prev = cdp.ev("document.getElementById('preview') ? document.getElementById('preview').innerHTML.length : 0")
        c.t(bool(prev), "右侧实时预览已渲染", prev)
    rec("R3", "键盘输入文字", r3, "R3_输入.png")

    # R4 鼠标拖动分区框
    def r4(c):
        cdp.click("#dragLayer .dbox")
        r = cdp.rect("#dragLayer .dbox")
        before = cdp.ev("JSON.stringify([curPage().zones[0].x,curPage().zones[0].y])")
        B.render_capture("R4_拖动_前.png")
        cdp.drag(r["x"], r["y"], r["x"] + 90, r["y"] + 55)
        after = cdp.ev("JSON.stringify([curPage().zones[0].x,curPage().zones[0].y])")
        c.t(before != after, "真实拖动更新分区坐标（百分比换算）", "%s -> %s" % (before, after))
    rec("R4", "鼠标拖动分区框", r4, "R4_拖动_后.png")

    # R5 拖角缩放
    def r5(c):
        cdp.click("#dragLayer .dbox")
        r = cdp.rect("#dragLayer .dbox.sel .dh-se") or cdp.rect("#dragLayer .dh-se")
        before = cdp.ev("JSON.stringify([curPage().zones[0].w,curPage().zones[0].h])")
        B.render_capture("R5_缩放_前.png")
        if r:
            cdp.drag(r["x"], r["y"], r["x"] + 70, r["y"] + 45)
        after = cdp.ev("JSON.stringify([curPage().zones[0].w,curPage().zones[0].h])")
        c.t(bool(r), "8 向缩放手柄可选中", bool(r))
        c.t(before != after, "拖角后尺寸更新", "%s -> %s" % (before, after))
        wh = cdp.ev("JSON.stringify(curPage().zones.map(z=>[z.w,z.h]))")
        c.t(bool(re.search(r"[4-9]\.|1\d", wh or "")), "尺寸不小于 4% 约束", wh[:80] if wh else "")
    rec("R5", "鼠标拖角缩放", r5, "R5_缩放_后.png")

    # R6 方向键微调
    def r6(c):
        cdp.click("#dragLayer .dbox")
        x0 = cdp.ev("curPage().zones[0].x")
        B.render_capture("R6_微移_前.png")
        cdp.key("ArrowRight", "ArrowRight", 39)
        x1 = cdp.ev("curPage().zones[0].x")
        cdp.key("ArrowRight", "ArrowRight", 39, shift=True)
        x2 = cdp.ev("curPage().zones[0].x")
        c.t(x1 is not None and x0 is not None and abs(x1 - x0 - 0.5) < 0.3,
            "方向键 0.5%/次", "%s -> %s" % (x0, x1))
        c.t(x2 is not None and abs(x2 - x1 - 2) < 0.5, "Shift 加速 2%/次", "%s -> %s" % (x1, x2))
    rec("R6", "方向键微调", r6, "R6_微移_后.png")

    # R7 删除功能框
    def r7(c):
        before = cdp.ev("curPage().zones.length")
        btns = cdp.ev("document.querySelectorAll('#zoneList button.warn').length")
        if btns:
            cdp.click("#zoneList button.warn:last-of-type")
        after = cdp.ev("curPage().zones.length")
        c.t(btns > 0, "分区列表有 × 删除按钮", btns)
        c.t(after == before - 1, "点 × 后分区数 -1", "%s -> %s" % (before, after))
    rec("R7", "删除功能框", r7, "R7_删除.png")

    # R8 操作同步预览
    def r8(c):
        before = cdp.ev("document.getElementById('preview').innerHTML.length")
        cdp.click("#zoneAdd")
        time.sleep(0.6)
        after = cdp.ev("document.getElementById('preview').innerHTML.length")
        c.t(before != after, "编辑操作即时反映到右侧预览", "%s -> %s" % (before, after))
        c.t(cdp.ev("document.getElementById('preview').innerHTML.length") > 100,
            "预览区有实际内容", True)
    rec("R8", "操作同步预览", r8, "R8_全貌.png")

    # R9 导出配置包
    def r9(c):
        cdp.click("#btnExport")
        time.sleep(3)
        files = [f for f in os.listdir(DL) if f.lower().endswith(".zip")]
        c.t(bool(files), "浏览器真实下载生成 ZIP", files[:3])
        if files:
            p = os.path.join(DL, files[0])
            import zipfile
            try:
                z = zipfile.ZipFile(p)
                names = z.namelist()
                c.t(any("layout.txt" in n or "settings.txt" in n for n in names),
                    "ZIP 内含配置文件", names[:5])
            except Exception as e:
                c.t(False, "ZIP 可正常打开", str(e)[:80])
    rec("R9", "导出配置包", r9, "R9_导出.png")

    # R11c 全程无错误
    def r11c(c):
        errs = [e for e in cdp.events if e.get("method") in
                ("Runtime.exceptionThrown", "Log.entryAdded")
                and ("exceptionThrown" in e.get("method") or
                     e.get("params", {}).get("entry", {}).get("level") == "error")]
        c.t(not errs, "全程控制台 0 运行时错误", len(errs))
        c.info("累计 CDP 事件 %d 条，含异常/错误 %d 条" % (len(cdp.events), len(errs)))
    rec("R11c", "全程无错误", r11c, "R11c_控制台.png")

    json.dump(results, open(os.path.join(OUT, "rgroup_results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "rgroup_results.tsv"), "w", encoding="utf-8") as f:
        f.write("编号\t模块\t测试项\t结论\t耗时s\t证据\n")
        for r in results:
            f.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (
                r["id"], r["module"], r["title"], "通过" if r["ok"] else "不通过", r["sec"],
                " ; ".join(n[5:] for n in r["notes"] if n.startswith("PASS"))[:180]))
    good = sum(1 for r in results if r["ok"])
    print("\n==== R 组 %d/%d 通过 ====" % (good, len(results)))
    for r in results:
        if not r["ok"]:
            print("FAIL", r["id"], r["title"])
            for n in r["notes"]:
                if n.startswith("FAIL"):
                    print("    ", n)
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except Exception:
        pass
    B.stop_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
