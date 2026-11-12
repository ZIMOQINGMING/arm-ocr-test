/* MediaBoard v3 - 离线 ZIP 导出工具（存储法，不压缩）
 * 供 editor.html 使用；也可在 node 里 require 做验证。
 * UMD-lite: 浏览器挂 window.MBZip，node 挂 module.exports。
 */
(function (root, factory) {
  var m = factory();
  if (typeof module !== "undefined" && module.exports) { module.exports = m; }
  root.MBZip = m;
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var CRC_TABLE = (function () {
    var t = new Array(256), c, n, k;
    for (n = 0; n < 256; n++) {
      c = n;
      for (k = 0; k < 8; k++) { c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; }
      t[n] = c >>> 0;
    }
    return t;
  }());
  function crc32(bytes) {
    var c = 0xFFFFFFFF, i;
    for (i = 0; i < bytes.length; i++) { c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8); }
    return (c ^ 0xFFFFFFFF) >>> 0;
  }
  // str -> Uint8Array (UTF-8)
  function utf8(str) {
    if (typeof TextEncoder !== "undefined") { return new TextEncoder().encode(str); }
    var out = [], i, c;
    for (i = 0; i < str.length; i++) {
      c = str.charCodeAt(i);
      if (c < 0x80) { out.push(c); }
      else if (c < 0x800) { out.push(0xC0 | c >> 6, 0x80 | c & 0x3F); }
      else { out.push(0xE0 | c >> 12, 0x80 | (c >> 6) & 0x3F, 0x80 | c & 0x3F); }
    }
    return new Uint8Array(out);
  }
  function u16(v) { return [v & 0xFF, (v >> 8) & 0xFF]; }
  function u32(v) { return [v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF]; }
  function concat(arrs) {
    var total = 0, i, r, off;
    for (i = 0; i < arrs.length; i++) { total += arrs[i].length; }
    r = new Uint8Array(total);
    off = 0;
    for (i = 0; i < arrs.length; i++) { r.set(arrs[i], off); off += arrs[i].length; }
    return r;
  }
  function dosTime(d) {
    var t = d ? new Date(d) : new Date();
    var date = ((t.getFullYear() - 1980) & 0x7F) << 9 | ((t.getMonth() + 1) & 0xF) << 5 | (t.getDate() & 0x1F);
    var time = (t.getHours() & 0x1F) << 11 | (t.getMinutes() & 0x3F) << 5 | ((t.getSeconds() / 2) & 0x1F);
    return { date: date, time: time };
  }
  // files: [{name:"a/b.txt", content:"..."}] -> Uint8Array (zip, store mode)
  function build(files) {
    var now = dosTime();
    var locals = [], centrals = [], offset = 0, i;
    for (i = 0; i < files.length; i++) {
      var nameB = utf8(files[i].name);
      var dataB = utf8(files[i].content);
      var crc = crc32(dataB);
      var local = concat([
        new Uint8Array(u32(0x04034B50)),           // local file header signature
        new Uint8Array(u16(20)),                   // version needed
        new Uint8Array(u16(0x0800)),              // flags: bit11 = 文件名 UTF-8
        new Uint8Array(u16(0)),                    // method: store
        new Uint8Array(u16(now.time)), new Uint8Array(u16(now.date)),
        new Uint8Array(u32(crc)),
        new Uint8Array(u32(dataB.length)),         // compressed
        new Uint8Array(u32(dataB.length)),         // uncompressed
        new Uint8Array(u16(nameB.length)), new Uint8Array(u16(0)),
        nameB, dataB
      ]);
      locals.push(local);
      centrals.push(concat([
        new Uint8Array(u32(0x02014B50)),           // central dir signature
        new Uint8Array(u16(20)), new Uint8Array(u16(20)),
        new Uint8Array(u16(0x0800)), new Uint8Array(u16(0)),
        new Uint8Array(u16(now.time)), new Uint8Array(u16(now.date)),
        new Uint8Array(u32(crc)),
        new Uint8Array(u32(dataB.length)), new Uint8Array(u32(dataB.length)),
        new Uint8Array(u16(nameB.length)), new Uint8Array(u16(0)),
        new Uint8Array(u16(0)), new Uint8Array(u16(0)), new Uint8Array(u16(0)),
        new Uint8Array(u32(0)),
        new Uint8Array(u32(offset)),
        nameB
      ]));
      offset += local.length;
    }
    var central = concat(centrals);
    var end = concat([
      new Uint8Array(u32(0x06054B50)),
      new Uint8Array(u16(0)), new Uint8Array(u16(0)),
      new Uint8Array(u16(files.length)), new Uint8Array(u16(files.length)),
      new Uint8Array(u32(central.length)),
      new Uint8Array(u32(offset)),
      new Uint8Array(u16(0))
    ]);
    return concat([concat(locals), central, end]);
  }
  // 触发浏览器下载
  function download(files, filename) {
    var bytes = build(files);
    var blob = new Blob([bytes], { type: "application/zip" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename || "mediaboard-config.zip";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 400);
  }
  return { build: build, download: download, crc32: crc32, utf8: utf8 };
}));
