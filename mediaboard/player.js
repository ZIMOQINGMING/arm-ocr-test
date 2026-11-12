/* MediaBoard v2 - 麒麟V10 离网多媒体看板（LEDvision 风格全功能版）
 * 依赖: 仅系统自带 chromium (83+)。无网络、无外部库。ES2017 语法。
 * 功能: 多节目页轮播 / 分区(文件·文本·时钟·计时) / 进出场切换特效 /
 *       滚动字幕 5 种效果 + 字体字号调节 / 自定义字体包(fonts/) /
 *       背景图色 + 背景音乐 / 通知插播 / 定时关屏(防烧屏)。
 */
(function () {
  "use strict";
  var P = window.PLAYLIST || {};
  var stage, msgBox;
  var pageIdx = 0, pageTimer = null, currentZones = [], pages = [];

  function setState(s) {
    var el = document.getElementById("mb-state");
    if (el) { el.textContent = s; }
  }
  window.addEventListener("error", function (e) {
    setState("error:" + (e.message || "unknown"));
  });

  function truthy(v) {
    return v === true || v === 1 || v === "1" || v === "yes" || v === "true";
  }
  function num(v, d) { var n = parseFloat(v); return isFinite(n) ? n : d; }
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function isVideo(src) { return /\.(mp4|webm|ogg|ogv|mov|mkv|m4v)$/i.test(src); }
  function fontCss(o, dSize) {
    return (truthy(o.bold) ? "bold " : "") + (truthy(o.italic) ? "italic " : "")
      + num(o.size, dSize) + "vh '" + (o.font || "sans-serif")
      + "','Noto Sans CJK SC','WenQuanYi Micro Hei',sans-serif";
  }

  // ---------- 自定义字体包（mediaboard/fonts/ 下的 ttf/otf/woff） ----------
  (P.fontfaces || []).forEach(function (f) {
    try {
      var s = document.createElement("style");
      s.textContent = "@font-face{font-family:'" + f.family + "';"
        + "src:url('" + f.url + "') format('" + (f.format || "truetype") + "');}";
      document.head.appendChild(s);
    } catch (e) { /* ignore */ }
  });

  // ---------- 通用跑马灯（水平整行循环 / 垂直整块循环，无缝） ----------
  function makeMarquee(host, inner, opts) {
    var speed = Math.max(5, num(opts.speed, opts.vertical ? 40 : 90));
    var anim = null;
    function stop() { if (anim) { try { anim.cancel(); } catch (e) {} anim = null; } }
    function build() {
      stop();
      var probe = document.createElement("div");
      probe.style.cssText = "position:absolute;visibility:hidden;pointer-events:none;white-space:nowrap;font:" + (opts.font || "");
      host.appendChild(probe);
      var unit, dist, i, d;
      if (opts.vertical) {
        opts.lines.forEach(function (ln) {
          d = document.createElement("div");
          d.style.whiteSpace = "nowrap";
          d.textContent = ln;
          probe.appendChild(d);
        });
        unit = probe.offsetHeight;
        if (unit <= 0) { host.removeChild(probe); return; }
        dist = host.clientHeight + unit;
        inner.innerHTML = "";
        var n = Math.min(200, Math.ceil(dist / unit) + 1);
        for (i = 0; i < n; i++) {
          opts.lines.forEach(function (ln) {
            d = document.createElement("div");
            d.style.whiteSpace = "nowrap";
            d.textContent = ln;
            inner.appendChild(d);
          });
        }
        anim = inner.animate(
          [{ transform: "translateY(" + host.clientHeight + "px)" }, { transform: "translateY(" + (-unit) + "px)" }],
          { duration: dist / speed * 1000, iterations: Infinity, easing: "linear" });
      } else {
        var line = opts.lines.join(opts.sep != null ? String(opts.sep) : "　　") + (opts.sep != null ? String(opts.sep) : "　　");
        probe.textContent = line;
        unit = probe.offsetWidth;
        if (unit <= 0) { host.removeChild(probe); return; }
        dist = host.clientWidth + unit;
        var rep = Math.min(200, Math.ceil(dist / unit) + 1);
        inner.textContent = new Array(rep + 1).join(line);
        anim = inner.animate(
          [{ transform: "translateX(" + host.clientWidth + "px)" }, { transform: "translateX(" + (-unit) + "px)" }],
          { duration: dist / speed * 1000, iterations: Infinity, easing: "linear" });
      }
      host.removeChild(probe);
    }
    var t0 = setTimeout(build, 60);
    if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
      document.fonts.ready.then(function () { clearTimeout(t0); build(); });
    }
    return { rebuild: build };
  }

  // ---------- 切换特效（对齐 LEDvision 进场/出场覆盖类特效） ----------
  var TLIST = ["fade", "cover-l", "cover-r", "cover-u", "cover-d",
    "wipe-l", "wipe-r", "wipe-u", "wipe-d", "wipe-lu", "wipe-ru"];
  function pickTransition() {
    var t = P.transition || "fade";
    if (t === "random") { return TLIST[Math.floor(Math.random() * TLIST.length)]; }
    return TLIST.indexOf(t) >= 0 ? t : "fade";
  }
  function animFrames(eff) {
    switch (eff) {
      case "cover-l": return [{ transform: "translateX(-100%)" }, { transform: "translateX(0)" }];
      case "cover-r": return [{ transform: "translateX(100%)" }, { transform: "translateX(0)" }];
      case "cover-u": return [{ transform: "translateY(-100%)" }, { transform: "translateY(0)" }];
      case "cover-d": return [{ transform: "translateY(100%)" }, { transform: "translateY(0)" }];
      case "wipe-l": return [{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0 0 0)" }];
      case "wipe-r": return [{ clipPath: "inset(0 0 0 100%)" }, { clipPath: "inset(0 0 0 0)" }];
      case "wipe-u": return [{ clipPath: "inset(0 0 100% 0)" }, { clipPath: "inset(0 0 0 0)" }];
      case "wipe-d": return [{ clipPath: "inset(100% 0 0 0)" }, { clipPath: "inset(0 0 0 0)" }];
      case "wipe-lu": return [{ clipPath: "polygon(0% 0%,0% 0%,0% 0%,0% 0%,0% 0%,0% 0%)" },
        { clipPath: "polygon(0% 0%,100% 0%,100% 55%,55% 100%,0% 100%,0% 0%)" }];
      case "wipe-ru": return [{ clipPath: "polygon(100% 0%,100% 0%,100% 0%,100% 0%,100% 0%,100% 0%)" },
        { clipPath: "polygon(0% 0%,100% 0%,100% 100%,45% 100%,0% 45%,0% 0%)" }];
      default: return [{ opacity: 0 }, { opacity: 1 }];
    }
  }

  function dimLabel(text) {
    var d = document.createElement("div");
    d._mbLabel = true;
    d.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;display:flex;"
      + "align-items:center;justify-content:center;color:#666;background:#111;"
      + "font:2.5vh 'Noto Sans CJK SC',sans-serif;";
    d.textContent = text;
    return d;
  }

  // ---------- 媒体分区：独立轮播 + 切换特效 + 停留期闪烁 ----------
  function makeMediaZone(z, el) {
    if (!z.slides || !z.slides.length) {
      el.appendChild(dimLabel("分区[" + z.name + "] 待放素材"));
      return;
    }
    var idx = 0, rotateTimer = null, alive = true;
    function next() {
      if (!alive || !el.isConnected) { alive = false; return; }
      idx = (idx + 1) % z.slides.length;
      show();
    }
    function show() {
      if (rotateTimer) { clearTimeout(rotateTimer); rotateTimer = null; }
      if (!alive || !el.isConnected) { alive = false; return; }
      var src = z.slides[idx];
      var fit = P.fill || "contain";
      var node, i;
      if (isVideo(src)) {
        node = document.createElement("video");
        node.autoplay = true;
        node.muted = (P.sound === false);
        node.onended = next;
        node.onerror = function () { rotateTimer = setTimeout(next, 4000); };
      } else {
        node = document.createElement("img");
        node.onerror = function () { rotateTimer = setTimeout(next, 4000); };
      }
      node.src = src;
      node.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;"
        + "object-fit:" + fit + ";background:#000";
      var eff = pickTransition();
      var dur = clamp(num(P.transitionTime, 0.8), 0, 5);
      // 旧画面退场（fade=交叉淡出；覆盖/擦除类=旧画面原地不动被盖住）
      var olds = [];
      for (i = 0; i < el.children.length; i++) {
        if (!el.children[i]._mbLabel) { olds.push(el.children[i]); }
      }
      if (eff === "fade" && dur > 0) {
        olds.forEach(function (o) {
          try { o.animate([{ opacity: 1 }, { opacity: 0 }],
            { duration: Math.round(dur * 1000), easing: "ease-out", fill: "forwards" }); } catch (e) {}
        });
      }
      el.appendChild(node);
      if (dur > 0 && eff !== "none") {
        try { node.animate(animFrames(eff),
          { duration: Math.round(dur * 1000), easing: "ease-out", fill: "forwards" }); } catch (e) {}
      }
      setTimeout(function () {
        olds.forEach(function (o) { if (o.parentNode === el) { el.removeChild(o); } });
      }, Math.round(dur * 1000) + 150);
      if (isVideo(src)) {
        var pr = node.play();
        if (pr && pr.catch) { pr.catch(function () {}); }
      } else {
        rotateTimer = setTimeout(next,
          clamp(num(z.duration, num(P.duration, 10)), 1, 86400) * 1000);
      }
      if (truthy(P.twinkle) && !isVideo(src)) {
        try { node.animate([{ opacity: 1 }, { opacity: 0.35 }, { opacity: 1 }],
          { duration: 1100, iterations: Infinity }); } catch (e) {}
      }
    }
    z._next = next;
    show();
  }

  // ---------- 文本窗（对齐 LEDvision 多行文本窗：字体/字号/颜色/对齐/效果） ----------
  function makeTextZone(z, el) {
    var t = z.text || {};
    var content = t.content || "";
    if (!content.trim()) {
      el.appendChild(dimLabel("文本窗[" + z.name + "] 缺 text.txt"));
      return;
    }
    var lines = String(content).replace(/\r/g, "").split("\n")
      .filter(function (s) { return s.trim() !== ""; });
    if (!lines.length) { el.appendChild(dimLabel("文本窗[" + z.name + "] 内容为空")); return; }
    var eff = t.effect || "static";
    var fcss = fontCss(t, 6);
    el.style.background = t.bgcolor || "rgba(0,0,0,0.45)";

    if (eff === "scroll-left" || eff === "scroll-up") {
      var inner = document.createElement("div");
      inner.style.cssText = "position:absolute;white-space:nowrap;will-change:transform;"
        + "color:" + (t.color || "#ffffff") + ";font:" + fcss + ";"
        + (eff === "scroll-up" ? "line-height:" + clamp(num(t.linespacing, 1.5), 1, 3) + "em;" : "");
      el.appendChild(inner);
      makeMarquee(el, inner, {
        lines: lines, speed: t.speed, vertical: eff === "scroll-up", sep: "　　", font: fcss
      });
      return;
    }
    if (eff === "typewriter") {
      var boxT = document.createElement("div");
      boxT.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;"
        + "display:flex;align-items:center;justify-content:center;padding:1vh 2vh;box-sizing:border-box;"
        + "text-align:" + (t.align || "center") + ";white-space:pre-wrap;"
        + "color:" + (t.color || "#ffffff") + ";font:" + fcss + ";";
      el.appendChild(boxT);
      var chars = Array.from(String(content).replace(/\r/g, ""));
      var cps = clamp(num(t.speed, 6), 0.5, 50);
      var ms = Math.round(1000 / cps);
      var i = 0, iv = null;
      function step() {
        if (!el.isConnected) { if (iv) { clearInterval(iv); } return; }
        i++;
        boxT.textContent = chars.slice(0, i).join("");
        if (i >= chars.length) {
          clearInterval(iv); iv = null;
          setTimeout(function () {
            if (!el.isConnected) { return; }
            i = 0; boxT.textContent = "";
            iv = setInterval(step, ms);
          }, 3000);
        }
      }
      iv = setInterval(step, ms);
      return;
    }
    var box = document.createElement("div");
    box.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;"
      + "display:flex;flex-direction:column;align-items:center;justify-content:center;"
      + "padding:1vh 2vh;box-sizing:border-box;text-align:" + (t.align || "center")
      + ";white-space:pre-wrap;color:" + (t.color || "#ffffff") + ";font:" + fcss + ";"
      + "line-height:" + clamp(num(t.linespacing, 1.5), 1, 3) + ";";
    box.textContent = String(content).replace(/\r/g, "");
    if (eff === "blink") {
      try { box.animate([{ opacity: 1 }, { opacity: 0.15 }, { opacity: 1 }],
        { duration: 900, iterations: Infinity }); } catch (e) {}
    }
    el.appendChild(box);
  }

  // ---------- 时钟窗（数字多种格式 / SVG 表盘） ----------
  var WEEKS = ["日", "一", "二", "三", "四", "五", "六"];
  function makeClock(z, el) {
    var c = z.clock || {};
    if ((c.mode || "digital") === "dial") { makeDialClock(el, c); return; }
    var presets = {
      datetime: "{Y}-{M}-{D} {h}:{m}:{s}",
      date: "{Y}-{M}-{D}",
      time: "{h}:{m}:{s}",
      week: "{Y}-{M}-{D} 星期{W}",
      weektime: "星期{W} {h}:{m}:{s}"
    };
    var pat = presets[c.format] || c.format || presets.datetime;
    el.style.cssText += ";display:flex;align-items:center;justify-content:center;"
      + "color:" + (c.color || "#ffffff") + ";background:" + (c.bgcolor || "rgba(0,0,0,0.55)")
      + ";font:" + fontCss(c, 4.5) + ";";
    function render() {
      var d = new Date();
      el.textContent = pat
        .replace(/\{Y\}/g, d.getFullYear())
        .replace(/\{M\}/g, pad2(d.getMonth() + 1))
        .replace(/\{D\}/g, pad2(d.getDate()))
        .replace(/\{h\}/g, pad2(d.getHours()))
        .replace(/\{m\}/g, pad2(d.getMinutes()))
        .replace(/\{s\}/g, pad2(d.getSeconds()))
        .replace(/\{W\}/g, WEEKS[d.getDay()]);
    }
    render();
    var iv = setInterval(function () {
      if (el.isConnected) { render(); } else { clearInterval(iv); }
    }, 200);
  }
  function makeDialClock(el, c) {
    el.style.cssText += ";display:flex;align-items:center;justify-content:center;"
      + "color:" + (c.color || "#ffffff") + ";background:" + (c.bgcolor || "rgba(0,0,0,0.55)") + ";";
    var NS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    var face = document.createElementNS(NS, "circle");
    face.setAttribute("cx", "50"); face.setAttribute("cy", "50"); face.setAttribute("r", "47");
    face.setAttribute("fill", "none"); face.setAttribute("stroke", "currentColor");
    face.setAttribute("stroke-width", "2.5");
    svg.appendChild(face);
    var i, a;
    for (i = 0; i < 12; i++) {
      var tk = document.createElementNS(NS, "line");
      a = i * 30 * Math.PI / 180;
      tk.setAttribute("x1", 50 + Math.sin(a) * 40); tk.setAttribute("y1", 50 - Math.cos(a) * 40);
      tk.setAttribute("x2", 50 + Math.sin(a) * 44); tk.setAttribute("y2", 50 - Math.cos(a) * 44);
      tk.setAttribute("stroke", "currentColor");
      tk.setAttribute("stroke-width", i % 3 === 0 ? "3" : "1.5");
      svg.appendChild(tk);
    }
    function hand(len, w) {
      var h = document.createElementNS(NS, "line");
      h.setAttribute("x1", "50"); h.setAttribute("y1", "50");
      h.setAttribute("x2", "50"); h.setAttribute("y2", String(50 - len));
      h.setAttribute("stroke", "currentColor");
      h.setAttribute("stroke-width", String(w));
      h.setAttribute("stroke-linecap", "round");
      svg.appendChild(h);
      return h;
    }
    var hh = hand(24, 4.5), mh = hand(35, 3), sh = hand(40, 1.5);
    var cap = document.createElementNS(NS, "circle");
    cap.setAttribute("cx", "50"); cap.setAttribute("cy", "50"); cap.setAttribute("r", "2.5");
    cap.setAttribute("fill", "currentColor");
    svg.appendChild(cap);
    el.appendChild(svg);
    requestAnimationFrame(function () {
      var s = Math.min(el.clientWidth, el.clientHeight) * 0.86;
      svg.setAttribute("width", String(Math.max(10, s)));
      svg.setAttribute("height", String(Math.max(10, s)));
    });
    function tick() {
      if (!el.isConnected) { clearInterval(iv); return; }
      var d = new Date();
      var sec = d.getSeconds() + d.getMilliseconds() / 1000;
      sh.setAttribute("transform", "rotate(" + sec * 6 + " 50 50)");
      mh.setAttribute("transform", "rotate(" + (d.getMinutes() + sec / 60) * 6 + " 50 50)");
      hh.setAttribute("transform", "rotate(" + ((d.getHours() % 12) + d.getMinutes() / 60) * 30 + " 50 50)");
    }
    tick();
    var iv = setInterval(tick, 200);
  }

  // ---------- 计时窗（倒计时到目标时刻 / 正计时） ----------
  function parseTarget(str) {
    if (!str) { return null; }
    var m = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$/.exec(String(str).trim());
    if (!m) { return null; }
    return new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0));
  }
  function makeCountdown(z, el) {
    var cd = z.countdown || {};
    var target = parseTarget(cd.target);
    var start = Date.now();
    var size = num(cd.size, 4.5);
    el.style.cssText += ";display:flex;flex-direction:column;align-items:center;justify-content:center;"
      + "color:" + (cd.color || "#ffffff") + ";background:" + (cd.bgcolor || "rgba(0,0,0,0.55)") + ";";
    var fam = "'" + (cd.font || "sans-serif") + "','Noto Sans CJK SC',sans-serif";
    if (cd.title) {
      var title = document.createElement("div");
      title.style.cssText = "font:" + (truthy(cd.bold) ? "bold " : "") + (size * 0.45) + "vh " + fam + ";opacity:.85;margin-bottom:1vh;";
      title.textContent = cd.title;
      el.appendChild(title);
    }
    var big = document.createElement("div");
    big.style.cssText = "font:bold " + size + "vh " + fam + ";";
    el.appendChild(big);
    function render() {
      if (target) {
        var diff = target.getTime() - Date.now();
        if (diff <= 0) { big.textContent = "0天 00:00:00"; return; }
        var sec = Math.floor(diff / 1000);
        var days = Math.floor(sec / 86400);
        big.textContent = days + "天 " + pad2(Math.floor(sec % 86400 / 3600))
          + ":" + pad2(Math.floor(sec % 3600 / 60)) + ":" + pad2(sec % 60);
      } else {
        var up = Math.floor((Date.now() - start) / 1000);
        var d2 = Math.floor(up / 86400);
        big.textContent = (d2 > 0 ? d2 + "天 " : "")
          + pad2(Math.floor(up % 86400 / 3600)) + ":"
          + pad2(Math.floor(up % 3600 / 60)) + ":" + pad2(up % 60);
      }
    }
    render();
    var iv = setInterval(function () {
      if (el.isConnected) { render(); } else { clearInterval(iv); }
    }, 250);
  }

  // ---------- 节目页 ----------
  function makeZone(z) {
    var el = document.createElement("div");
    el.style.cssText = "position:absolute;overflow:hidden;background:#000;"
      + "left:" + z.x + "%;top:" + z.y + "%;width:" + z.w + "%;height:" + z.h + "%;";
    el._mbZone = z;
    stage.appendChild(el);
    if (z.clock) { makeClock(z, el); }
    else if (z.countdown) { makeCountdown(z, el); }
    else if (z.text) { makeTextZone(z, el); }
    else { makeMediaZone(z, el); }
    currentZones.push(z);
    return el;
  }
  function renderPage(i) {
    if (pageTimer) { clearTimeout(pageTimer); pageTimer = null; }
    currentZones = [];
    stage.innerHTML = "";
    pageIdx = i;
    pages[i].zones.forEach(makeZone);
    updateDiag();
    if (pages.length > 1 && num(pages[i].duration, 0) > 0) {
      pageTimer = setTimeout(switchPage, num(pages[i].duration, 0) * 1000);
    }
  }
  function switchPage() {
    if (pageTimer) { clearTimeout(pageTimer); pageTimer = null; }
    // 不依赖动画 onfinish（chromium 版本/虚拟时钟下不稳定），用 transition + 定时器
    stage.style.transition = "opacity 350ms linear";
    stage.style.opacity = "0";
    setTimeout(function () {
      renderPage((pageIdx + 1) % pages.length);
      stage.style.opacity = "1";
      setTimeout(function () { stage.style.transition = ""; }, 420);
    }, 360);
  }

  // ---------- 背景 / 背景音乐 ----------
  function applyBackground() {
    if (P.bgcolor) { document.body.style.background = P.bgcolor; }
    var bg = document.getElementById("bg");
    if (P.bgimage) {
      bg.style.display = "block";
      bg.style.backgroundImage = "url('" + P.bgimage + "')";
    }
  }
  function applyBgm() {
    if (!P.bgmusic) { return; }
    try {
      var a = document.createElement("audio");
      a.src = P.bgmusic; a.loop = true; a.autoplay = true;
      a.volume = clamp(num(P.bgmusicVol, 0.6), 0, 1);
      document.body.appendChild(a);
      var pr = a.play();
      if (pr && pr.catch) { pr.catch(function () {}); }
    } catch (e) {}
  }

  // ---------- 通知插播（顶部横幅，N 分钟后自动消失） ----------
  function applyNotify() {
    var nf = P.notify;
    if (!nf || !nf.text) { return; }
    var bar = document.getElementById("notify");
    var inner = document.getElementById("notify-inner");
    var h = clamp(num(nf.height, 10), 4, 30);
    var fcss = "bold " + (h * 0.5) + "vh sans-serif";
    bar.style.display = "block";
    bar.style.height = h + "vh";
    bar.style.background = nf.bgcolor || "#c00000";
    bar.style.color = nf.color || "#ffffff";
    inner.style.cssText = "position:absolute;white-space:nowrap;will-change:transform;"
      + "line-height:" + h + "vh;font:" + fcss + ";color:inherit;";
    makeMarquee(bar, inner, {
      lines: [String(nf.text).replace(/\r/g, "")], speed: 80, vertical: false, sep: "　　", font: fcss
    });
    setTimeout(function () { bar.style.display = "none"; },
      clamp(num(nf.minutes, 5), 0.2, 1440) * 60000);
  }

  // ---------- 定时关屏（防烧屏，黑屏时段） ----------
  function applyScreenOff() {
    var win = P.screenOff;
    if (!win) { return; }
    var m = /^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$/.exec(String(win).replace(/\s/g, ""));
    if (!m) { return; }
    var a = (+m[1]) * 60 + (+m[2]), b = (+m[3]) * 60 + (+m[4]);
    function check() {
      var d = new Date();
      var now = d.getHours() * 60 + d.getMinutes();
      var off = a <= b ? (now >= a && now < b) : (now >= a || now < b);
      document.getElementById("screenoff").style.display = off ? "block" : "none";
    }
    check();
    setInterval(check, 20000);
  }

  // ---------- 底部滚动字幕（5 种效果 + 字体字号调节） ----------
  function applyTicker() {
    var tk = P.ticker || {};
    if (!tk.text || !String(tk.text).trim()) { return; }
    var lines = String(tk.text).replace(/\r/g, "").split("\n")
      .filter(function (s) { return s.trim() !== ""; });
    if (!lines.length) { return; }
    var bar = document.getElementById("ticker");
    var inner = document.getElementById("ticker-inner");
    var h = clamp(num(tk.height, 9), 3, 30);
    var eff = tk.effect || "scroll-left";
    var fcss = fontCss(tk, 5.5);
    bar.style.display = "block";
    bar.style.height = h + "vh";
    bar.style.background = tk.bgcolor || "rgba(0,0,0,0.72)";
    bar.style.color = tk.color || "#ffff00";
    var centered = "display:block;width:100%;text-align:center;line-height:" + h + "vh;"
      + "font:" + fcss + ";color:inherit;overflow:hidden;white-space:nowrap;";
    if (eff === "static" || eff === "blink") {
      inner.style.cssText = centered;
      if (eff === "static") {
        inner.style.textOverflow = "ellipsis";
      } else {
        try { inner.animate([{ opacity: 1 }, { opacity: 0.15 }, { opacity: 1 }],
          { duration: 900, iterations: Infinity }); } catch (e) {}
      }
      inner.textContent = lines.join("　");
      return;
    }
    if (eff === "typewriter") {
      inner.style.cssText = centered;
      var chars = Array.from(lines.join("　"));
      var cps = clamp(num(tk.speed, 6), 0.5, 50);
      var ms = Math.round(1000 / cps);
      var i = 0, iv = null;
      function step() {
        i++;
        inner.textContent = chars.slice(0, i).join("");
        if (i >= chars.length) {
          clearInterval(iv); iv = null;
          setTimeout(function () {
            i = 0; inner.textContent = "";
            iv = setInterval(step, ms);
          }, 3000);
        }
      }
      iv = setInterval(step, ms);
      return;
    }
    // scroll-left / scroll-up
    inner.style.cssText = "position:absolute;white-space:nowrap;will-change:transform;"
      + "color:inherit;font:" + fcss + ";"
      + (eff === "scroll-up" ? "line-height:" + clamp(num(tk.linespacing, 1.4), 1, 3) + "em;"
         : "line-height:" + h + "vh;");
    makeMarquee(bar, inner, {
      lines: lines, speed: tk.speed, vertical: eff === "scroll-up",
      sep: tk.sep != null ? String(tk.sep) : "　　●　　", font: fcss
    });
  }

  // ---------- 诊断（?diag=1 显示分区像素矩形） ----------
  var diagOn = location.search.indexOf("diag") >= 0;
  function updateDiag() {
    if (!diagOn) { return; }
    var d = document.getElementById("mb-diag");
    if (!d) {
      d = document.createElement("pre");
      d.id = "mb-diag";
      d.style.cssText = "position:fixed;top:0;left:0;z-index:98;color:#0f0;background:#000;"
        + "font:12px monospace;margin:0;padding:3px;opacity:.85";
      document.body.appendChild(d);
    }
    var rects = [];
    for (var i = 0; i < stage.children.length; i++) {
      var el2 = stage.children[i];
      var z = el2._mbZone;
      var r = el2.getBoundingClientRect();
      rects.push((z && z.name ? z.name : "?") + "=" + Math.round(r.left) + "," + Math.round(r.top)
        + "," + Math.round(r.width) + "x" + Math.round(r.height));
    }
    d.textContent = "viewport=" + window.innerWidth + "x" + window.innerHeight
      + " dpr=" + (window.devicePixelRatio || 1)
      + " page=" + (pageIdx + 1) + "/" + pages.length
      + " | " + rects.join(" | ");
  }

  // ---------- 启动 ----------
  function init() {
    stage = document.getElementById("stage");
    msgBox = document.getElementById("msg");
    applyBackground();
    var fallback = [{ duration: 0, zones: [{ name: "全屏", x: 0, y: 0, w: 100, h: 100, slides: P.slides || [] }] }];
    pages = (P.pages && P.pages.length) ? P.pages : fallback;
    var hasContent = pages.some(function (pg) {
      return pg.zones.some(function (z) {
        return z.clock || z.countdown || z.text || (z.slides && z.slides.length);
      });
    });
    if (!hasContent) {
      msgBox.textContent = "MediaBoard 已就绪：请把素材放进 content 目录后重启";
    }
    renderPage(0);
    applyTicker();
    applyNotify();
    applyScreenOff();
    applyBgm();
    document.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight") { return; }
      for (var i = 0; i < currentZones.length; i++) {
        var z = currentZones[i];
        if (!z.clock && !z.countdown && !z.text && z._next) { z._next(); return; }
      }
    });
    if (P.reloadMinutes > 0) {
      setInterval(function () { location.reload(); }, P.reloadMinutes * 60000);
    }
    setState("ready");
  }
  init();
})();
