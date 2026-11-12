/* MediaBoard player - 麒麟V10 离网播放板（分区版）
 * 依赖: 仅系统自带 chromium。无网络、无外部库。
 * 兼容: ES2017 语法上限 (chromium 83+ 可用)。
 * 分区模型对齐 LEDvision: 屏幕 -> 节目窗口(分区) -> 播放内容, 各分区同时独立播放。
 */
(function () {
  "use strict";
  var P = window.PLAYLIST || {};
  var stage = document.getElementById("stage");
  var msgBox = document.getElementById("msg");

  function isVideo(src) {
    return /\.(mp4|webm|ogg|ogv|mov|mkv|m4v)$/i.test(src);
  }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  // ---- 时钟窗口 ----
  function makeClock(el) {
    el.style.display = "flex";
    el.style.alignItems = "center";
    el.style.justifyContent = "center";
    el.style.color = "#ffffff";
    el.style.background = "rgba(0,0,0,0.55)";
    el.style.font = "bold 4.5vh sans-serif";
    function tick() {
      var d = new Date();
      el.textContent = d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
        + " " + pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
    }
    tick();
    setInterval(tick, 1000);
  }

  // ---- 媒体分区：独立轮播 ----
  function makeZone(z) {
    var el = document.createElement("div");
    el.style.cssText = "position:absolute;overflow:hidden;background:#000;"
      + "left:" + z.x + "%;top:" + z.y + "%;width:" + z.w + "%;height:" + z.h + "%;";
    stage.appendChild(el);
    if (z.clock) { makeClock(el); return; }

    var idx = 0, timer = null;
    function next() {
      if (!z.slides.length) { return; }
      idx = (idx + 1) % z.slides.length;
      show();
    }
    function show() {
      if (timer) { clearTimeout(timer); timer = null; }
      el.innerHTML = "";
      if (!z.slides.length) { return; }
      var src = z.slides[idx];
      var node;
      if (isVideo(src)) {
        node = document.createElement("video");
        node.src = src;
        node.autoplay = true;
        node.muted = (P.sound === false);
        node.style.cssText = "width:100%;height:100%;object-fit:contain;background:#000";
        node.onended = next;
        node.onerror = function () { timer = setTimeout(next, 4000); };
        var pr;
        el.appendChild(node);
        pr = node.play();
        if (pr && pr.catch) { pr.catch(function () {}); }
      } else {
        node = document.createElement("img");
        node.src = src;
        node.style.cssText = "width:100%;height:100%;object-fit:contain;background:#000";
        node.onerror = function () { timer = setTimeout(next, 4000); };
        el.appendChild(node);
        timer = setTimeout(next, (z.duration || P.duration || 10) * 1000);
      }
    }
    z._next = next;
    show();
  }

  var zones = P.zones || [];
  // 兼容模式：无分区定义时全屏轮播 content/ 顶层素材
  if (!zones.length) {
    zones = [{ x: 0, y: 0, w: 100, h: 100, slides: P.slides || [] }];
  }
  var hasContent = zones.some(function (z) { return z.clock || (z.slides && z.slides.length); });
  if (!hasContent) {
    msgBox.textContent = "MediaBoard 已就绪：请把素材放进 content 目录后重启";
  }
  zones.forEach(makeZone);

  // 键盘手动翻页（作用于第一个媒体分区）
  document.addEventListener("keydown", function (e) {
    var z0 = null;
    zones.forEach(function (z) { if (!z0 && !z.clock && z._next) { z0 = z; } });
    if (!z0) { return; }
    if (e.key === "ArrowRight") { z0._next(); }
  });

  // ---- 滚动字幕（底部，全宽） ----
  var tk = P.ticker || {};
  if (tk.text && tk.text.length) {
    var bar = document.getElementById("ticker");
    var inner = document.getElementById("ticker-inner");
    bar.style.display = "flex";
    bar.style.color = tk.color || "#ffff00";
    bar.style.background = tk.bgcolor || "rgba(0,0,0,0.72)";
    bar.style.font = "bold 5.5vh sans-serif";
    var sep = "　　●　　";
    inner.textContent = tk.text + sep + tk.text + sep;
    var speed = tk.speed || 60;
    var secs = Math.max(10, inner.textContent.length * speed / 10);
    inner.style.animationDuration = secs + "s";
  }

  // 定时整页刷新
  if (P.reloadMinutes > 0) {
    setInterval(function () { location.reload(); }, P.reloadMinutes * 60000);
  }
})();
