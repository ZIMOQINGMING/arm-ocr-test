/* MediaBoard v3 - 麒麟V10 离网多媒体看板（LEDvision 全功能 + 视觉增强版）
 * 依赖: 仅系统自带 chromium (83+)。无网络、无外部服务。qr.js 为本包自带(MIT)。
 * v3 新增: 性能档位(PERF) / 柔和转场(fade-zoom·blur-fade·slide-soft) /
 *   文字阴影描边·渐变底·卡片圆角投影·tabular-nums / 字幕两端渐隐 /
 *   Ken Burns 缓推 / 分区 PADDING·MARGIN·ALIGN-V·RADIUS·CARD /
 *   12x12 栅格坐标 / 图片组九宫格 / 二维码窗 / 公告列表窗(本地JSON刷新) /
 *   SVG图标·装饰线 / ?selftest=1 自检 / 编辑器 postMessage 联动。
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
  // 视觉增强片段（分区级 SHADOW/STROKE/TABNUM，Chromium 83 全支持）
  function visCss(z) {
    var s = "";
    if (truthy(z.shadow) && !perfLow()) { s += "text-shadow:0 .25vh 1vh rgba(0,0,0,.65);"; }
    if (truthy(z.stroke)) { s += "-webkit-text-stroke:.14vh rgba(0,0,0,.4);"; }
    if (truthy(z.tabnum)) { s += "font-variant-numeric:tabular-nums;"; }
    return s;
  }

  // ---------- 性能档位 ----------
  var PERF = P.perf || "high";
  function perfLow() { return PERF === "low"; }
  function perfMid() { return PERF === "mid"; }

  // ---------- 自定义字体包 ----------
  var fontsInjected = false;
  function injectFonts() {
    if (fontsInjected) { return; }
    fontsInjected = true;
    (P.fontfaces || []).forEach(function (f) {
      try {
        var s = document.createElement("style");
        s.textContent = "@font-face{font-family:'" + f.family + "';"
          + "src:url('" + f.url + "') format('" + (f.format || "truetype") + "');}";
        document.head.appendChild(s);
      } catch (e) {}
    });
  }
  injectFonts();

  // ---------- SVG 图标集（内联零依赖） ----------
  var ICONS = {
    info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="10.5" x2="12" y2="16"/><circle cx="12" cy="7" r="1.1" fill="currentColor" stroke="none"/>',
    warn: '<path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9.5" x2="12" y2="15"/><circle cx="12" cy="17.3" r="1" fill="currentColor" stroke="none"/>',
    star: '<path d="M12 2 L14.6 8.6 L21.5 9 L16 13.6 L18 20.5 L12 16.6 L6 20.5 L8 13.6 L2.5 9 L9.4 8.6 Z"/>',
    clock: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="12" x2="12" y2="6"/><line x1="12" y1="12" x2="16" y2="14"/>',
    horn: '<path d="M3 10 v4 h3 l5 4 V6 l-5 4 Z"/><path d="M15 9 a4 4 0 0 1 0 6"/><path d="M17.5 7 a7 7 0 0 1 0 10"/>',
    check: '<circle cx="12" cy="12" r="10"/><path d="M8 12 l3 3 l5 -6"/>',
    flag: '<path d="M5 3 v18"/><path d="M5 4 h12 l-3 4 l3 4 h-12"/>'
  };
  function iconSvg(name, hVh) {
    if (!ICONS[name]) { return null; }
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", hVh + "vh");
    svg.setAttribute("height", hVh + "vh");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.7");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("stroke-linecap", "round");
    svg.innerHTML = ICONS[name];
    return svg;
  }
  // 装饰线 / 角标（伪元素式附加 div，零成本精致度）
  function applyDecor(z, el) {
    if (z.decor === "line") {
      var ln = document.createElement("div");
      ln.style.cssText = "position:absolute;top:0;left:0;width:100%;height:.5vh;"
        + "background:linear-gradient(90deg,rgba(255,255,255,0) 0%,rgba(255,255,255,.85) 18%,rgba(255,255,255,0) 90%);z-index:2;pointer-events:none;";
      el.appendChild(ln);
    } else if (z.decor === "corner") {
      ["t l", "t r", "b l", "b r"].forEach(function (pos) {
        var d = document.createElement("div");
        var t = pos.charAt(0) === "t", l = pos.charAt(2) === "l";
        d.style.cssText = "position:absolute;" + (t ? "top:0.8vh;" : "bottom:0.8vh;")
          + (l ? "left:0.8vh;" : "right:0.8vh;") + "width:2.2vh;height:2.2vh;pointer-events:none;"
          + "border-" + (t ? "top" : "bottom") + ":2px solid rgba(255,255,255,.55);"
          + "border-" + (l ? "left" : "right") + ":2px solid rgba(255,255,255,.55);";
        el.appendChild(d);
      });
    }
  }

  // ---------- 通用跑马灯 ----------
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

  // ---------- 切换特效（14 种） ----------
  var TLIST = ["fade", "fade-zoom", "blur-fade", "slide-soft",
    "cover-l", "cover-r", "cover-u", "cover-d",
    "wipe-l", "wipe-r", "wipe-u", "wipe-d", "wipe-lu", "wipe-ru"];
  function pickTransition() {
    var t = P.transition || "fade";
    if (perfLow()) { return "fade"; }              // 低档位统一降级为淡入淡出
    if (perfMid() && t === "blur-fade") { return "fade"; } // 中档位模糊转场降级
    if (t === "random") { return TLIST[Math.floor(Math.random() * TLIST.length)]; }
    return TLIST.indexOf(t) >= 0 ? t : "fade";
  }
  var EASE_STD = "cubic-bezier(.4,0,.2,1)";
  function animFrames(eff) {
    switch (eff) {
      case "fade-zoom": return [{ opacity: 0, transform: "scale(1.06)" }, { opacity: 1, transform: "scale(1)" }];
      case "blur-fade": return [{ opacity: 0, filter: "blur(14px)" }, { opacity: 1, filter: "blur(0px)" }];
      case "slide-soft": return [{ opacity: 0, transform: "translateX(4%)" }, { opacity: 1, transform: "translateX(0)" }];
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

  // ---------- 媒体分区：轮播 + 特效 + Ken Burns；或 GROUP=grid 九宫格 ----------
  function makeMediaZone(z, el) {
    if (!z.slides || !z.slides.length) {
      el.appendChild(dimLabel("分区[" + z.name + "] 待放素材"));
      return;
    }
    if (z.group === "grid") { makeGridZone(z, el); return; }
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
      var node, i, media;
      var eff = pickTransition();
      var dur = clamp(num(P.transitionTime, 0.8), 0, 5);
      // 外层 wrapper 承接转场，内层 img/video 承接 Ken Burns，互不冲突
      node = document.createElement("div");
      node.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;background:#000";
      if (isVideo(src)) {
        media = document.createElement("video");
        media.autoplay = true;
        media.muted = (P.sound === false);
        media.onended = next;
        media.onerror = function () { rotateTimer = setTimeout(next, 4000); };
        media.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;object-fit:" + fit;
        node.appendChild(media);
      } else {
        media = document.createElement("img");
        media.onerror = function () { rotateTimer = setTimeout(next, 4000); };
        media.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;"
          + "object-fit:" + fit + ";background:#000";
        node.appendChild(media);
        // Ken Burns 缓推（静图变"活"）；低档位关闭
        if (truthy(P.kenburns) && !perfLow() && !perfMid()) {
          try {
            media.animate(
              [{ transform: "scale(1) translate(0,0)" }, { transform: "scale(1.07) translate(-1.4%,-.8%)" }],
              { duration: Math.min(clamp(num(z.duration, num(P.duration, 10)), 1, 86400), 40) * 1000,
                easing: "ease-out", fill: "forwards" });
          } catch (e) {}
        }
      }
      media.src = src;
      var olds = [];
      for (i = 0; i < el.children.length; i++) {
        if (!el.children[i]._mbLabel) { olds.push(el.children[i]); }
      }
      if ((eff === "fade" || eff === "fade-zoom") && dur > 0) {
        olds.forEach(function (o) {
          try { o.animate([{ opacity: 1 }, { opacity: 0 }],
            { duration: Math.round(dur * 1000), easing: "ease-out", fill: "forwards" }); } catch (e) {}
        });
      }
      el.appendChild(node);
      if (dur > 0 && eff !== "none") {
        try { node.animate(animFrames(eff),
          { duration: Math.round(dur * 1000), easing: EASE_STD, fill: "forwards" }); } catch (e) {}
      }
      setTimeout(function () {
        olds.forEach(function (o) { if (o.parentNode === el) { el.removeChild(o); } });
      }, Math.round(dur * 1000) + 150);
      if (isVideo(src)) {
        var pr = media.play();
        if (pr && pr.catch) { pr.catch(function () {}); }
      } else {
        rotateTimer = setTimeout(next,
          clamp(num(z.duration, num(P.duration, 10)), 1, 86400) * 1000);
      }
      if (truthy(P.twinkle) && !isVideo(src)) {
        try { media.animate([{ opacity: 1 }, { opacity: 0.35 }, { opacity: 1 }],
          { duration: 1100, iterations: Infinity }); } catch (e) {}
      }
    }
    z._next = next;
    show();
  }

  // 图片组九宫格：分区内全部素材一次性网格铺开（不再轮播）
  function makeGridZone(z, el) {
    var n = z.slides.length;
    var cols = clamp(Math.round(num(z.groupcols, Math.ceil(Math.sqrt(n)))), 1, 8);
    var rows = Math.ceil(n / cols);
    var gap = 0.8; // vh
    var grid = document.createElement("div");
    grid.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;"
      + "display:grid;padding:" + (num(z.padding, 0) + 0.8) + "vh;box-sizing:border-box;"
      + "grid-template-columns:repeat(" + cols + ",1fr);grid-template-rows:repeat(" + rows + ",1fr);"
      + "gap:" + gap + "vh;background:" + (z.gradient ? "" : "#101010") + ";";
    z.slides.slice(0, cols * rows).forEach(function (src) {
      var cell = document.createElement("div");
      cell.style.cssText = "position:relative;overflow:hidden;background:#000;border-radius:.6vh;"
        + (truthy(z.card) && !perfLow() ? "box-shadow:0 .4vh 1.2vh rgba(0,0,0,.3);" : "");
      if (isVideo(src)) {
        var v = document.createElement("video");
        v.autoplay = true; v.muted = true; v.loop = true;
        // 注意: #stage img/video 全局 CSS 带 position:absolute，格内必须显式改回 static 否则四图叠在左上角
        v.style.cssText = "position:static;display:block;width:100%;height:100%;object-fit:" + (P.fill || "contain");
        v.src = src;
        cell.appendChild(v);
        var pr = v.play(); if (pr && pr.catch) { pr.catch(function () {}); }
      } else {
        var im = document.createElement("img");
        im.style.cssText = "position:static;display:block;width:100%;height:100%;object-fit:" + (P.fill || "contain");
        im.src = src;
        cell.appendChild(im);
      }
      grid.appendChild(cell);
    });
    el.appendChild(grid);
  }

  // ---------- 文本窗 ----------
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
    if (!z.gradient) { el.style.background = t.bgcolor || "rgba(0,0,0,0.45)"; }
    var extra = visCss(z);
    var pad = num(z.padding, 0);
    var alignv = z.alignv === "top" ? "flex-start" : (z.alignv === "bottom" ? "flex-end" : "center");

    if (eff === "scroll-left" || eff === "scroll-up") {
      var inner = document.createElement("div");
      inner.style.cssText = "position:absolute;white-space:nowrap;will-change:transform;"
        + "color:" + (t.color || "#ffffff") + ";font:" + fcss + ";" + extra
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
        + "display:flex;align-items:center;justify-content:center;"
        + "padding:" + (pad + 1) + "vh " + (pad + 2) + "vh;box-sizing:border-box;"
        + "text-align:" + (t.align || "center") + ";white-space:pre-wrap;"
        + "color:" + (t.color || "#ffffff") + ";font:" + fcss + ";" + extra;
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
      + "display:flex;flex-direction:column;align-items:center;justify-content:" + alignv + ";"
      + "padding:" + (pad + 1) + "vh " + (pad + 2) + "vh;box-sizing:border-box;"
      + "text-align:" + (t.align || "center") + ";white-space:pre-wrap;"
      + "color:" + (t.color || "#ffffff") + ";font:" + fcss + ";"
      + "line-height:" + clamp(num(t.linespacing, 1.5), 1, 3) + ";" + extra;
    // 图标行（可选）
    if (z.icon && ICONS[z.icon]) {
      var irow = document.createElement("div");
      irow.style.cssText = "display:flex;align-items:center;margin-bottom:1.2vh;color:" + (t.color || "#ffffff") + ";";
      var isize = clamp(num(t.size, 6) * 1.4, 2, 30);
      var ic = iconSvg(z.icon, isize);
      if (ic) { irow.appendChild(ic); }
      if (z.icontext) {
        var ilab = document.createElement("span");
        ilab.style.cssText = "margin-left:1vh;font:" + fcss;
        ilab.textContent = z.icontext;
        irow.appendChild(ilab);
      }
      box.appendChild(irow);
    }
    box.textContent = String(content).replace(/\r/g, "");
    if (eff === "blink") {
      try { box.animate([{ opacity: 1 }, { opacity: 0.15 }, { opacity: 1 }],
        { duration: 900, iterations: Infinity }); } catch (e) {}
    }
    el.appendChild(box);
  }

  // ---------- 时钟窗 ----------
  var WEEKS = ["日", "一", "二", "三", "四", "五", "六"];
  function alignvCss(z) {
    return z.alignv === "top" ? "flex-start" : (z.alignv === "bottom" ? "flex-end" : "center");
  }
  function makeClock(z, el) {
    var c = z.clock || {};
    if ((c.mode || "digital") === "dial") { makeDialClock(z, el, c); return; }
    var presets = {
      datetime: "{Y}-{M}-{D} {h}:{m}:{s}",
      date: "{Y}-{M}-{D}",
      time: "{h}:{m}:{s}",
      week: "{Y}-{M}-{D} 星期{W}",
      weektime: "星期{W} {h}:{m}:{s}"
    };
    var pat = presets[c.format] || c.format || presets.datetime;
    var pad = num(z.padding, 0);
    el.style.cssText += ";display:flex;align-items:center;justify-content:center;"
      + "color:" + (c.color || "#ffffff") + ";background:" + (z.gradient ? "" : (c.bgcolor || "rgba(0,0,0,0.55)"))
      + ";font:" + fontCss(c, 4.5) + ";" + visCss(z) + "font-variant-numeric:tabular-nums;"
      + "padding:" + pad + "vh;box-sizing:border-box;";
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
  function makeDialClock(z, el, c) {
    var pad = num(z.padding, 0);
    el.style.cssText += ";display:flex;align-items:center;justify-content:center;"
      + "color:" + (c.color || "#ffffff") + ";background:" + (z.gradient ? "" : (c.bgcolor || "rgba(0,0,0,0.55)"))
      + ";padding:" + pad + "vh;box-sizing:border-box;";
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

  // ---------- 计时窗 ----------
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
    var pad = num(z.padding, 0);
    el.style.cssText += ";display:flex;flex-direction:column;align-items:center;justify-content:" + alignvCss(z) + ";"
      + "color:" + (cd.color || "#ffffff") + ";background:" + (z.gradient ? "" : (cd.bgcolor || "rgba(0,0,0,0.55)"))
      + ";padding:" + pad + "vh;box-sizing:border-box;";
    var fam = "'" + (cd.font || "sans-serif") + "','Noto Sans CJK SC',sans-serif";
    if (cd.title) {
      var title = document.createElement("div");
      title.style.cssText = "font:" + (truthy(cd.bold) ? "bold " : "") + (size * 0.45) + "vh " + fam
        + ";opacity:.85;margin-bottom:1vh;" + visCss(z);
      title.textContent = cd.title;
      el.appendChild(title);
    }
    var big = document.createElement("div");
    big.style.cssText = "font:bold " + size + "vh " + fam + ";font-variant-numeric:tabular-nums;" + visCss(z);
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

  // ---------- 二维码窗（qr.js 本地生成，离网可用，中文支持） ----------
  function makeQrZone(z, el) {
    var q = z.qr || {};
    var text = String(q.content || "").trim();
    if (!text) { el.appendChild(dimLabel("二维码窗[" + z.name + "] 缺 text.txt")); return; }
    if (typeof window.qrcode !== "function") {
      el.appendChild(dimLabel("二维码窗[" + z.name + "] 缺 qr.js 库文件")); return;
    }
    var pad = num(z.padding, 0);
    el.style.cssText += ";background:" + (z.gradient ? "" : (q.bgcolor || "#ffffff"))
      + ";padding:" + pad + "vh;box-sizing:border-box;";
    var qr = null;
    for (var t = 1; t <= 40 && !qr; t++) {
      try {
        var g = window.qrcode(t, q.ecl || "M");
        g.addData(text);
        g.make();
        qr = g;
      } catch (e) {}
    }
    if (!qr) { el.appendChild(dimLabel("二维码内容过长，生成失败")); return; }
    var wrap = document.createElement("div");
    wrap.style.cssText = "width:100%;height:100%;display:flex;flex-direction:column;"
      + "align-items:center;justify-content:" + alignvCss(z) + ";";
    var cv = document.createElement("canvas");
    var n = qr.getModuleCount();
    var quiet = 4; // 静区
    var scale = 8;
    cv.width = cv.height = (n + quiet * 2) * scale;
    var ctx = cv.getContext("2d");
    ctx.fillStyle = q.bgcolor || "#ffffff";
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = q.color || "#111111";
    for (var r = 0; r < n; r++) {
      for (var c2 = 0; c2 < n; c2++) {
        if (qr.isDark(r, c2)) {
          ctx.fillRect((c2 + quiet) * scale, (r + quiet) * scale, scale, scale);
        }
      }
    }
    cv.style.cssText = "max-width:100%;max-height:100%;object-fit:contain;";
    wrap.appendChild(cv);
    if (q.title) {
      var lab = document.createElement("div");
      lab.style.cssText = "margin-top:.8vh;color:" + (q.titlecolor || (q.color || "#111111"))
        + ";font:2.2vh 'Noto Sans CJK SC','WenQuanYi Micro Hei',sans-serif;" + visCss(z);
      lab.textContent = q.title;
      wrap.appendChild(lab);
    }
    el.appendChild(wrap);
  }

  // ---------- 公告列表窗（本地 text.txt 或 data/*.json 定时刷新） ----------
  function makeNoticeZone(z, el) {
    var n0 = z.notice || {};
    var items = (String(n0.content || "").replace(/\r/g, "").split("\n"))
      .filter(function (s) { return s.trim() !== ""; });
    var pad = num(z.padding, 0);
    var fcss = fontCss(n0, 3.2);
    var icon = z.icon || n0.icon;
    function render(list) {
      if (!list.length) { el.appendChild(dimLabel("公告窗[" + z.name + "] 内容为空")); return; }
      var box = document.createElement("div");
      box.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;"
        + "display:flex;flex-direction:column;justify-content:" + alignvCss(z) + ";"
        + "padding:" + (pad + 1.2) + "vh " + (pad + 1.6) + "vh;box-sizing:border-box;"
        + "overflow:hidden;color:" + (n0.color || "#ffffff") + ";"
        + (z.gradient ? "" : "background:" + (n0.bgcolor || "rgba(0,0,0,0.55)") + ";") + visCss(z);
      if (n0.title) {
        var hd = document.createElement("div");
        hd.style.cssText = "flex:0 0 auto;display:flex;align-items:center;margin-bottom:1vh;"
          + "padding-bottom:.6vh;border-bottom:1px solid rgba(255,255,255,.25);"
          + "color:" + (n0.titlecolor || n0.color || "#ffffff") + ";font:" + (truthy(n0.bold) ? "bold " : "") + num(n0.size, 3.2) * 1.15 + "vh '"
          + (n0.font || "sans-serif") + "','Noto Sans CJK SC',sans-serif;" + visCss(z);
        var hi = iconSvg(icon || "horn", num(n0.size, 3.2) * 1.15);
        if (hi) { hd.appendChild(hi); }
        var ht = document.createElement("span");
        ht.style.cssText = "margin-left:.8vh;";
        ht.textContent = n0.title;
        hd.appendChild(ht);
        box.appendChild(hd);
      }
      var needScroll = false;
      list.forEach(function (it, i) {
        var row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;margin:.55vh 0;font:" + fcss + ";";
        if (!n0.title) {
          var idx = document.createElement("span");
          idx.style.cssText = "flex:0 0 auto;margin-right:.8vh;opacity:.75;";
          idx.textContent = "•";
          row.appendChild(idx);
        }
        var tx = document.createElement("span");
        tx.style.cssText = "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
        tx.textContent = it;
        row.appendChild(tx);
        box.appendChild(row);
      });
      el.appendChild(box);
      // 超出分区高度 -> 整块自动上滚
      requestAnimationFrame(function () {
        if (box.scrollHeight > el.clientHeight + 4) {
          needScroll = true;
          el.innerHTML = "";
          var inner = document.createElement("div");
          inner.style.cssText = "position:absolute;left:0;top:0;width:100%;white-space:nowrap;"
            + "color:" + (n0.color || "#ffffff") + ";font:" + fcss + ";" + visCss(z);
          el.appendChild(inner);
          makeMarquee(el, inner, {
            lines: list, speed: num(n0.speed, 30), vertical: true, sep: "　　", font: fcss
          });
        }
        void needScroll;
      });
    }
    render(items);
    // DATASRC: data/*.json 定时刷新（离网本地数据源）
    if (n0.datasrc) {
      var refreshMs = clamp(num(n0.refresh, 0), 0, 1440) * 60000;
      function pull() {
        try {
          var xhr = new XMLHttpRequest();
          xhr.open("GET", n0.datasrc, true);
          xhr.onload = function () {
            try {
              var j = JSON.parse(xhr.responseText);
              var list = (Array.isArray(j) ? j : (j.items || [])).map(function (x) {
                return typeof x === "string" ? x : (x.text || x.title || "");
              }).filter(function (s) { return s; });
              if (list.length) { el.innerHTML = ""; render(list); }
            } catch (e) {}
          };
          xhr.onerror = function () {};
          xhr.send();
        } catch (e) {}
      }
      if (refreshMs > 0) { setInterval(pull, refreshMs); }
    }
  }

  // ---------- 节目页 ----------
  function zoneBoxCss(z) {
    var m = clamp(num(z.margin, 0), 0, 20);
    var css = "position:absolute;overflow:hidden;"
      + "left:" + (num(z.x, 0) + m) + "%;top:" + (num(z.y, 0) + m) + "%;"
      + "width:" + Math.max(2, num(z.w, 100) - 2 * m) + "%;height:" + Math.max(2, num(z.h, 100) - 2 * m) + "%;";
    if (z.radius) { css += "border-radius:" + clamp(num(z.radius, 1), 0, 10) + "vh;"; }
    else if (truthy(z.card)) { css += "border-radius:1.2vh;"; }
    if (truthy(z.card) && !perfLow()) { css += "box-shadow:0 1vh 2.4vh rgba(0,0,0,.35);"; }
    if (z.gradient) {
      var ab = String(z.gradient).split(",");
      var a = (ab[0] || "#101820").trim(), b = (ab[1] || ab[0] || "#1a3a6b").trim();
      css += "background:linear-gradient(135deg," + a + "," + b + ");";
    }
    return css;
  }
  function makeZone(z) {
    var el = document.createElement("div");
    el.style.cssText = zoneBoxCss(z);
    el._mbZone = z;
    stage.appendChild(el);
    if (z.clock) { makeClock(z, el); }
    else if (z.countdown) { makeCountdown(z, el); }
    else if (z.text) { makeTextZone(z, el); }
    else if (z.qr) { makeQrZone(z, el); }
    else if (z.notice) { makeNoticeZone(z, el); }
    else { makeMediaZone(z, el); }
    applyDecor(z, el);
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
    document.body.style.background = P.bgcolor || "#000";
    var bg = document.getElementById("bg");
    if (P.bgimage) {
      bg.style.display = "block";
      bg.style.backgroundImage = "url('" + P.bgimage + "')";
    } else {
      bg.style.display = "none";
      bg.style.backgroundImage = "";
    }
  }
  function applyBgm() {
    var old = document.getElementById("mb-bgm");
    if (old) { old.parentNode.removeChild(old); }
    if (!P.bgmusic) { return; }
    try {
      var a = document.createElement("audio");
      a.id = "mb-bgm";
      a.src = P.bgmusic; a.loop = true; a.autoplay = true;
      a.volume = clamp(num(P.bgmusicVol, 0.6), 0, 1);
      document.body.appendChild(a);
      var pr = a.play();
      if (pr && pr.catch) { pr.catch(function () {}); }
    } catch (e) {}
  }

  // ---------- 通知插播 ----------
  function applyNotify() {
    var bar = document.getElementById("notify");
    var inner = document.getElementById("notify-inner");
    bar.style.display = "none";
    var nf = P.notify;
    if (!nf || !nf.text) { return; }
    var h = clamp(num(nf.height, 10), 4, 30);
    var fcss = "bold " + (h * 0.5) + "vh sans-serif";
    bar.style.display = "block";
    bar.style.height = h + "vh";
    bar.style.background = nf.bgcolor || "#c00000";
    bar.style.color = nf.color || "#ffffff";
    inner.style.cssText = "position:absolute;white-space:nowrap;will-change:transform;"
      + "line-height:" + h + "vh;font:" + fcss + ";color:inherit;"
      + "text-shadow:0 .2vh .6vh rgba(0,0,0,.5);";
    makeMarquee(bar, inner, {
      lines: [String(nf.text).replace(/\r/g, "")], speed: 80, vertical: false, sep: "　　", font: fcss
    });
    setTimeout(function () { bar.style.display = "none"; },
      clamp(num(nf.minutes, 5), 0.2, 1440) * 60000);
  }

  // ---------- 定时关屏 ----------
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

  // ---------- 底部滚动字幕 ----------
  function applyTicker() {
    var tk = P.ticker || {};
    var bar = document.getElementById("ticker");
    var inner = document.getElementById("ticker-inner");
    bar.style.display = "none";
    if (!tk.text || !String(tk.text).trim()) { return; }
    var lines = String(tk.text).replace(/\r/g, "").split("\n")
      .filter(function (s) { return s.trim() !== ""; });
    if (!lines.length) { return; }
    var h = clamp(num(tk.height, 9), 3, 30);
    var eff = tk.effect || "scroll-left";
    var fcss = fontCss(tk, 5.5);
    bar.style.display = "block";
    bar.style.height = h + "vh";
    bar.style.background = tk.bgcolor || "rgba(0,0,0,0.72)";
    bar.style.color = tk.color || "#ffff00";
    // 两端渐隐（Chromium 83: -webkit-mask-image 可用；低档位关闭）
    bar.style.webkitMaskImage = bar.style.maskImage = "";
    if (truthy(tk.mask) && !perfLow()) {
      var mk = "linear-gradient(90deg,rgba(0,0,0,0),rgba(0,0,0,1) 4%,rgba(0,0,0,1) 96%,rgba(0,0,0,0))";
      try { bar.style.webkitMaskImage = mk; bar.style.maskImage = mk; } catch (e) {}
    }
    var shadowCss = perfLow() ? "" : "text-shadow:0 .2vh .8vh rgba(0,0,0,.7);";
    var centered = "display:block;width:100%;text-align:center;line-height:" + h + "vh;"
      + "font:" + fcss + ";color:inherit;overflow:hidden;white-space:nowrap;" + shadowCss;
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
    inner.style.cssText = "position:absolute;white-space:nowrap;will-change:transform;"
      + "color:inherit;font:" + fcss + ";" + shadowCss
      + (eff === "scroll-up" ? "line-height:" + clamp(num(tk.linespacing, 1.4), 1, 3) + "em;"
         : "line-height:" + h + "vh;");
    makeMarquee(bar, inner, {
      lines: lines, speed: tk.speed, vertical: eff === "scroll-up",
      sep: tk.sep != null ? String(tk.sep) : "　　●　　", font: fcss
    });
  }

  // ---------- 诊断 ----------
  var diagOn = location.search.indexOf("diag") >= 0 && location.search.indexOf("selftest") < 0;
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

  // ---------- 自检模式（?selftest=1：目标机拍照即证据） ----------
  function runSelftest() {
    var results = [];
    function add(name, ok, detail) {
      results.push({ name: name, ok: ok, detail: detail || "" });
    }
    add("WAAPI动画(el.animate)", typeof Element !== "undefined" && typeof Element.prototype.animate === "function", "特效引擎");
    add("CSS.supports", typeof CSS !== "undefined" && typeof CSS.supports === "function", "特性探测");
    if (typeof CSS !== "undefined" && CSS.supports) {
      add("clip-path 擦除转场", CSS.supports("clip-path", "inset(0 0 0 0)"));
      add("filter blur 模糊转场", CSS.supports("filter", "blur(2px)"));
      add("mask-image 字幕渐隐", CSS.supports("-webkit-mask-image", "linear-gradient(#000,#000)")
        || CSS.supports("mask-image", "linear-gradient(#000,#000)"));
      add("font-variant-numeric 等宽数字", CSS.supports("font-variant-numeric", "tabular-nums"));
      add("linear-gradient 渐变底", CSS.supports("background", "linear-gradient(135deg,#111,#222)")
        || CSS.supports("background-image", "linear-gradient(135deg,#111,#222)"));
      add("box-shadow 卡片投影", CSS.supports("box-shadow", "0 1px 2px rgba(0,0,0,.3)"));
      add("-webkit-text-stroke 描边", CSS.supports("-webkit-text-stroke", "1px #000"));
    }
    add("canvas 2D(二维码绘制)", (function () {
      try { return !!document.createElement("canvas").getContext("2d"); } catch (e) { return false; }
    })());
    add("二维码库 qr.js", typeof window.qrcode === "function");
    add("本地存储 localStorage", (function () {
      try { localStorage.setItem("mb_t", "1"); localStorage.removeItem("mb_t"); return true; }
      catch (e) { return false; }
    })());
    var v = document.createElement("video");
    add("H.264视频解码", /^(probably|maybe)$/.test(v.canPlayType('video/mp4; codecs="avc1.42E01E"'))
      ? v.canPlayType('video/mp4; codecs="avc1.42E01E"') : false, v.canPlayType('video/mp4; codecs="avc1.42E01E"'));
    add("MP3音频解码", /^(probably|maybe)$/.test(v.canPlayType("audio/mpeg")) ? v.canPlayType("audio/mpeg") : false);
    add("系统内存可见", !!(window.performance && performance.memory),
      performance && performance.memory ? Math.round(performance.memory.jsHeapSizeLimit / 1048576) + "MB上限" : "不可读(正常)");
    // 渲染结果页（大字，拍照即证据）
    document.body.innerHTML = "";
    var box = document.createElement("div");
    box.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;overflow:auto;"
      + "background:#0a0a0a;color:#eee;padding:2vh 3vh;box-sizing:border-box;"
      + "font:2.6vh 'Noto Sans CJK SC','WenQuanYi Micro Hei',sans-serif;cursor:default;";
    var title = document.createElement("h1");
    title.style.cssText = "font-size:4vh;margin:.5vh 0 1.5vh;color:#ffd54a;";
    title.textContent = "MediaBoard v3 自检报告";
    box.appendChild(title);
    var pass = 0;
    results.forEach(function (r) {
      var row = document.createElement("div");
      var ok = r.ok === true || /^(probably|maybe)/.test(String(r.ok));
      if (ok) { pass++; }
      row.style.cssText = "margin:.6vh 0;padding:.6vh 1vh;background:#151515;border-radius:.6vh;"
        + "display:flex;align-items:center;";
      var tag = document.createElement("span");
      tag.style.cssText = "flex:0 0 14vh;font-weight:bold;color:" + (ok ? "#4caf50" : "#ff5252") + ";";
      tag.textContent = ok ? "✔ 通过" : "✘ 不支持";
      var nm = document.createElement("span");
      nm.style.cssText = "flex:1;";
      nm.textContent = r.name + (r.detail ? "（" + r.detail + "）" : "");
      row.appendChild(tag); row.appendChild(nm);
      box.appendChild(row);
    });
    var sum = document.createElement("div");
    sum.style.cssText = "margin-top:2vh;font-size:3.4vh;font-weight:bold;color:"
      + (pass === results.length ? "#4caf50" : "#ffb300") + ";";
    sum.textContent = "自检结果: " + pass + "/" + results.length + " 项通过 · 性能档位:" + PERF;
    box.appendChild(sum);
    var tip = document.createElement("div");
    tip.style.cssText = "margin-top:1vh;color:#888;font-size:2vh;";
    tip.textContent = "字体包逐项加载校验：" + ((P.fontfaces || []).map(function (f) { return f.family; }).join("、") || "（未安装自定义字体）") + " —— 见下方字体行";
    box.appendChild(tip);
    var st = document.createElement("span");
    st.id = "mb-state";
    st.style.display = "none";
    box.appendChild(st);
    document.body.appendChild(box);
    document.title = "selftest " + pass + "/" + results.length;
    setState("selftest:" + pass + "/" + results.length);
    // @font-face 异步校验追加
    if (document.fonts && document.fonts.check) {
      document.fonts.ready.then(function () {
        (P.fontfaces || []).forEach(function (f) {
          var ok = false;
          try { ok = document.fonts.check("12px '" + f.family + "'"); } catch (e) {}
          var row = document.createElement("div");
          row.style.cssText = "margin:.6vh 0;padding:.6vh 1vh;background:#151515;border-radius:.6vh;display:flex;";
          var tag = document.createElement("span");
          tag.style.cssText = "flex:0 0 14vh;font-weight:bold;color:" + (ok ? "#4caf50" : "#ff5252") + ";";
          tag.textContent = ok ? "✔ 加载" : "✘ 失败";
          var nm = document.createElement("span");
          nm.textContent = "字体包: " + f.family;
          row.appendChild(tag); row.appendChild(nm);
          box.insertBefore(row, sum);
        });
      });
    }
  }

  // ---------- 编辑器联动（editor.html iframe postMessage） ----------
  window.mbApply = function (cfg) {
    try {
      P = cfg || {};
      PERF = P.perf || "high";
      document.body.className = "";
      injectFonts();
      var tb = document.getElementById("ticker");
      tb.style.display = "none";
      tb.style.webkitMaskImage = tb.style.maskImage = "";
      applyBackground();
      var fallback = [{ duration: 0, zones: [{ name: "全屏", x: 0, y: 0, w: 100, h: 100, slides: P.slides || [] }] }];
      pages = (P.pages && P.pages.length) ? P.pages : fallback;
      renderPage(0);
      applyTicker();
      applyNotify();
      setState("editor-live");
    } catch (e) { setState("error:" + (e.message || "apply")); }
  };
  window.addEventListener("message", function (ev) {
    if (ev.data && ev.data.mbConfig) { window.mbApply(ev.data.mbConfig); }
  });

  // ---------- 启动 ----------
  function init() {
    stage = document.getElementById("stage");
    msgBox = document.getElementById("msg");
    document.body.className = "perf-" + PERF;
    if (location.search.indexOf("selftest") >= 0) { runSelftest(); return; }
    applyBackground();
    var fallback = [{ duration: 0, zones: [{ name: "全屏", x: 0, y: 0, w: 100, h: 100, slides: P.slides || [] }] }];
    pages = (P.pages && P.pages.length) ? P.pages : fallback;
    var hasContent = pages.some(function (pg) {
      return pg.zones.some(function (z) {
        return z.clock || z.countdown || z.text || z.qr || z.notice || (z.slides && z.slides.length);
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
        if (!z.clock && !z.countdown && !z.text && !z.qr && !z.notice && z._next) { z._next(); return; }
      }
    });
    if (P.reloadMinutes > 0) {
      setInterval(function () { location.reload(); }, P.reloadMinutes * 60000);
    }
    setState("ready");
  }
  init();
})();
