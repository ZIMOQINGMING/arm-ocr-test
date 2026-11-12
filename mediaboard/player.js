/* MediaBoard player - 麒麟V10 离网播放板
 * 依赖: 仅系统自带 chromium。无网络、无外部库。
 * 兼容性: ES2017 语法上限 (chromium 83+ 可用)。
 */
(function () {
  "use strict";
  var P = window.PLAYLIST || {};
  var slides = P.slides || [];
  var duration = (P.duration || 10) * 1000;
  var sound = (P.sound !== false);
  var reloadMinutes = P.reloadMinutes || 0;
  var stage = document.getElementById("stage");
  var msgBox = document.getElementById("msg");
  var idx = 0;
  var timer = null;

  function msg(t) { msgBox.textContent = t || ""; }

  function isVideo(src) {
    return /\.(mp4|webm|ogg|ogv|mov|mkv|m4v)$/i.test(src);
  }

  function next() {
    if (!slides.length) { return; }
    idx = (idx + 1) % slides.length;
    show();
  }

  function prev() {
    if (!slides.length) { return; }
    idx = (idx - 1 + slides.length) % slides.length;
    show();
  }

  function show() {
    if (timer) { clearTimeout(timer); timer = null; }
    stage.innerHTML = "";
    if (!slides.length) {
      msg("MediaBoard 已就绪：请把图片/视频放进 content 目录后重启");
      return;
    }
    msg("");
    var src = slides[idx];
    if (isVideo(src)) {
      var v = document.createElement("video");
      v.src = src;
      v.autoplay = true;
      v.muted = !sound;
      v.onended = next;
      v.onerror = function () {
        msg("视频无法解码(建议H.264编码mp4)，4秒后跳过: " + src);
        timer = setTimeout(next, 4000);
      };
      stage.appendChild(v);
      var p = v.play();
      if (p && p.catch) { p.catch(function () {}); }
    } else {
      var im = document.createElement("img");
      im.src = src;
      im.onerror = function () {
        msg("图片加载失败，4秒后跳过: " + src);
        timer = setTimeout(next, 4000);
      };
      stage.appendChild(im);
      timer = setTimeout(next, duration);
    }
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") { next(); }
    else if (e.key === "ArrowLeft") { prev(); }
  });

  // 滚动字幕
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
    var speed = tk.speed || 60;              // px/s 的倒数权重，数值越大越慢
    var secs = Math.max(10, inner.textContent.length * speed / 10);
    inner.style.animationDuration = secs + "s";
  }

  // 定时整页刷新（拿到 content 目录的新内容，start.sh 会重新生成 playlist.js 后由看门狗重启）
  if (reloadMinutes > 0) {
    setInterval(function () { location.reload(); }, reloadMinutes * 60000);
  }

  show();
})();
