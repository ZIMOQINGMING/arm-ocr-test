#!/usr/bin/env bash
# MediaBoard 启动脚本（麒麟V10 离网播放板）
# 功能: 扫描 content/ 生成 playlist.js -> PPT 自动转图片(若有WPS/LibreOffice) -> chromium 全屏播放
# 看门狗: chromium 退出后 3 秒自动重开
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

# ---------- 读取设置 ----------
DURATION=10
SOUND=yes
RELOAD_MINUTES=30
TICKER_SPEED=60
TICKER_COLOR="#ffff00"
TICKER_BGCOLOR="rgba(0,0,0,0.72)"
if [ -f settings.txt ]; then
  while IFS='=' read -r k v; do
    case "$k" in
      DURATION) DURATION="$v";;
      SOUND) SOUND="$v";;
      RELOAD_MINUTES) RELOAD_MINUTES="$v";;
      TICKER_SPEED) TICKER_SPEED="$v";;
      TICKER_COLOR) TICKER_COLOR="$v";;
      TICKER_BGCOLOR) TICKER_BGCOLOR="$v";;
    esac
  done < settings.txt
fi
[ "$SOUND" = "yes" ] && SOUND_JS=true || SOUND_JS=false

# ---------- PPT 转图片（有转换工具才执行） ----------
convert_ppt() {
  local ppt="$1" base outdir
  base="$(basename "$ppt")"
  outdir="content/converted/${base%.*}"
  mkdir -p "$outdir"
  local conv=""
  for c in soffice libreoffice wpp wps; do
    command -v "$c" >/dev/null 2>&1 && conv="$c" && break
  done
  [ -z "$conv" ] && { echo "[PPT] 无转换工具，跳过 $base（请在电脑上另存为图片后放入）"; return 1; }
  "$conv" --headless --convert-to pdf --outdir /tmp "$ppt" >/dev/null 2>&1
  local pdf="/tmp/${base%.*}.pdf"
  [ -f "$pdf" ] || { echo "[PPT] PDF 转换失败: $base"; return 1; }
  if command -v pdftoppm >/dev/null 2>&1; then
    pdftoppm -r 100 -jpeg "$pdf" "$outdir/slide" >/dev/null 2>&1
  elif command -v gs >/dev/null 2>&1; then
    gs -dNOPAUSE -dBATCH -sDEVICE=jpeg -r100 -sOutputFile="$outdir/slide-%02d.jpg" "$pdf" >/dev/null 2>&1
  else
    echo "[PPT] 无 pdftoppm/gs，无法拆页: $base"; return 1
  fi
  rm -f "$pdf"
  echo "[PPT] 已转换: $base -> $outdir/"
}

if ls content/*.ppt content/*.pptx >/dev/null 2>&1; then
  for f in content/*.ppt content/*.pptx; do
    [ -f "$f" ] && convert_ppt "$f"
  done
fi

# ---------- 生成 playlist.js ----------
esc() { sed 's/\\/\\\\/g; s/"/\\"/g'; }
TICKER_TEXT=""
[ -f ticker.txt ] && TICKER_TEXT="$(tr '\n' ' ' < ticker.txt | esc)"
{
  echo "window.PLAYLIST={"
  echo "duration:$DURATION,"
  echo "sound:$SOUND_JS,"
  echo "reloadMinutes:$RELOAD_MINUTES,"
  printf 'ticker:{text:"%s",speed:%s,color:"%s",bgcolor:"%s"},\n' \
    "$TICKER_TEXT" "$TICKER_SPEED" "$TICKER_COLOR" "$TICKER_BGCOLOR"
  echo "slides:["
  find content -type f \
    \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" \
       -o -iname "*.webp" -o -iname "*.bmp" -o -iname "*.mp4" -o -iname "*.webm" \
       -o -iname "*.ogg" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.m4v" \) \
    | LC_ALL=C sort | while IFS= read -r f; do
        printf '"%s",\n' "$(printf '%s' "$f" | esc)"
      done
  echo "]"
  echo "};"
} > playlist.js
echo "[MediaBoard] playlist.js 已生成 ($(grep -c '^"' playlist.js) 个条目)"

# ---------- 测试模式：只生成 playlist.js，不启动 ----------
[ "${MEDIABOARD_TEST:-0}" = "1" ] && exit 0

# ---------- 找浏览器 ----------
CHROME=""
for c in chromium-browser chromium google-chrome; do
  command -v "$c" >/dev/null 2>&1 && CHROME="$c" && break
done
if [ -z "$CHROME" ]; then
  echo "[错误] 找不到 chromium 浏览器，无法播放"; exit 1
fi

# 关闭息屏/屏保（若有 xset）
command -v xset >/dev/null 2>&1 && { xset s off 2>/dev/null; xset -dpms 2>/dev/null; }

# ---------- 看门狗循环 ----------
echo "[MediaBoard] 启动 $CHROME 全屏播放 (Ctrl+C 停止)"
while true; do
  "$CHROME" --kiosk --noerrdialogs --disable-infobars \
    --disable-session-crashed-bubble --disable-restore-session-state \
    --autoplay-policy=no-user-gesture-required \
    "file://$DIR/player.html" >/dev/null 2>&1
  sleep 3
done
