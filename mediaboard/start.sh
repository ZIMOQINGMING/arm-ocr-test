#!/usr/bin/env bash
# MediaBoard v3 启动脚本（麒麟V10 离网多媒体看板 - LEDvision 全功能 + 视觉增强）
# 功能: 解析 layout.txt 多节目页/分区(含12x12栅格 g:语法) -> 生成 playlist.js + fonts.json
#       -> PPT/Word/Excel 自动转图 -> 字体包枚举 -> chromium 全屏播放
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

# ---------- 读取设置 ----------
DURATION=10
SOUND=no
RELOAD_MINUTES=30
FILL=contain
TRANSITION=fade
TRANSITION_TIME=0.8
TWINKLE=no
PAGE_DURATION=60
BGIMAGE=""
BGCOLOR=""
BGMUSIC=""
BGMUSIC_VOL=0.6
PERF=high
KENBURNS=no
TICKER_EFFECT=scroll-left
TICKER_SPEED=90
TICKER_FONT=""
TICKER_SIZE=5.5
TICKER_COLOR="#ffff00"
TICKER_BGCOLOR="#1a3a6b"
TICKER_BOLD=yes
TICKER_HEIGHT=9
TICKER_SEP=""
TICKER_MASK=yes
SCREEN_OFF=""
NOTIFY_MINUTES=5
if [ -f settings.txt ]; then
  while IFS='=' read -r k v; do
    # 剥离行内注释（仅"空格+#"形式；颜色值 #1a3a6b 前面无空格，不受影响）
    v="$(printf '%s' "$v" | sed 's/[[:space:]]\{1,\}#.*$//; s/[[:space:]]*$//')"
    case "$k" in
      DURATION) DURATION="$v";;
      SOUND) SOUND="$v";;
      RELOAD_MINUTES) RELOAD_MINUTES="$v";;
      FILL) FILL="$v";;
      TRANSITION) TRANSITION="$v";;
      TRANSITION_TIME) TRANSITION_TIME="$v";;
      TWINKLE) TWINKLE="$v";;
      PAGE_DURATION) PAGE_DURATION="$v";;
      BGIMAGE) BGIMAGE="$v";;
      BGCOLOR) BGCOLOR="$v";;
      BGMUSIC) BGMUSIC="$v";;
      BGMUSIC_VOL) BGMUSIC_VOL="$v";;
      PERF) PERF="$v";;
      KENBURNS) KENBURNS="$v";;
      TICKER_EFFECT) TICKER_EFFECT="$v";;
      TICKER_SPEED) TICKER_SPEED="$v";;
      TICKER_FONT) TICKER_FONT="$v";;
      TICKER_SIZE) TICKER_SIZE="$v";;
      TICKER_COLOR) TICKER_COLOR="$v";;
      TICKER_BGCOLOR) TICKER_BGCOLOR="$v";;
      TICKER_BOLD) TICKER_BOLD="$v";;
      TICKER_HEIGHT) TICKER_HEIGHT="$v";;
      TICKER_SEP) TICKER_SEP="$v";;
      TICKER_MASK) TICKER_MASK="$v";;
      SCREEN_OFF) SCREEN_OFF="$v";;
      NOTIFY_MINUTES) NOTIFY_MINUTES="$v";;
    esac
  done < settings.txt
fi
[ "$SOUND" = "yes" ] && SOUND_JS=true || SOUND_JS=false
case "$FILL" in cover|fill|contain|scale-down) ;; *) FILL="contain";; esac
case "$TRANSITION" in fade|fade-zoom|blur-fade|slide-soft|random|cover-l|cover-r|cover-u|cover-d|wipe-l|wipe-r|wipe-u|wipe-d|wipe-lu|wipe-ru|none) ;; *) TRANSITION="fade";; esac
case "$TRANSITION_TIME" in *[!0-9.]*) TRANSITION_TIME=0.8;; esac
case "$TWINKLE" in yes|1|true) TWINKLE_JS=true;; *) TWINKLE_JS=false;; esac
case "$PAGE_DURATION" in *[!0-9.]*) PAGE_DURATION=60;; esac
case "$TICKER_EFFECT" in scroll-left|scroll-up|blink|static|typewriter) ;; *) TICKER_EFFECT="scroll-left";; esac
case "$TICKER_SPEED" in *[!0-9.]*) TICKER_SPEED=90;; esac
case "$TICKER_SIZE" in *[!0-9.]*) TICKER_SIZE=5.5;; esac
case "$TICKER_BOLD" in yes|1|true) TICKER_BOLD_JS=true;; *) TICKER_BOLD_JS=false;; esac
case "$TICKER_HEIGHT" in *[!0-9.]*) TICKER_HEIGHT=9;; esac
case "$TICKER_SEP" in "") TICKER_SEP="　　●　　";; esac
case "$TICKER_MASK" in no|0|false) TICKER_MASK_JS=false;; *) TICKER_MASK_JS=true;; esac
case "$NOTIFY_MINUTES" in *[!0-9.]*) NOTIFY_MINUTES=5;; esac
case "$BGMUSIC_VOL" in *[!0-9.]*) BGMUSIC_VOL=0.6;; esac
case "$PERF" in high|mid|low) ;; *) PERF="high";; esac
case "$KENBURNS" in yes|1|true) KENBURNS_JS=true;; *) KENBURNS_JS=false;; esac
case "$SCREEN_OFF" in [0-2][0-9]:[0-5][0-9]-[0-2][0-9]:[0-5][0-9]) ;; *) SCREEN_OFF="";; esac
[ -n "$BGIMAGE" ] && [ ! -f "$BGIMAGE" ] && { echo "[设置] BGIMAGE 文件不存在, 忽略: $BGIMAGE"; BGIMAGE=""; }
[ -n "$BGMUSIC" ] && [ ! -f "$BGMUSIC" ] && { echo "[设置] BGMUSIC 文件不存在, 忽略: $BGMUSIC"; }

esc() { sed 's/\\/\\\\/g; s/"/\\"/g'; }
# 文本转 JS 字符串: 保留换行为 \n 转义
escape_text() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk 'BEGIN{ORS="\\n"} {print}'
}

# ---------- PPT/Word/Excel 转图片（有 WPS/LibreOffice 才执行） ----------
convert_doc() {
  local ppt="$1" base outdir d conv pdf
  base="$(basename "$ppt")"
  d="$(dirname "$ppt")"
  outdir="$d/converted/${base%.*}"
  mkdir -p "$outdir"
  conv=""
  for c in soffice libreoffice wpp wps; do
    command -v "$c" >/dev/null 2>&1 && conv="$c" && break
  done
  [ -z "$conv" ] && { echo "[转换] 无转换工具，跳过 $base（请在电脑上另存为图片后放入）"; return 1; }
  "$conv" --headless --convert-to pdf --outdir /tmp "$ppt" >/dev/null 2>&1
  pdf="/tmp/${base%.*}.pdf"
  [ -f "$pdf" ] || { echo "[转换] PDF 转换失败: $base"; return 1; }
  if command -v pdftoppm >/dev/null 2>&1; then
    pdftoppm -r 100 -jpeg "$pdf" "$outdir/slide" >/dev/null 2>&1
  elif command -v gs >/dev/null 2>&1; then
    gs -dNOPAUSE -dBATCH -sDEVICE=jpeg -r100 -sOutputFile="$outdir/slide-%02d.jpg" "$pdf" >/dev/null 2>&1
  else
    echo "[转换] 无 pdftoppm/gs，无法拆页: $base"; return 1
  fi
  rm -f "$pdf"
  echo "[转换] 已转换: $base -> $outdir/"
}
find content -type f \( -iname "*.ppt" -o -iname "*.pptx" -o -iname "*.doc" -o -iname "*.docx" -o -iname "*.xls" -o -iname "*.xlsx" \) -not -path "*/converted/*" 2>/dev/null \
  | while IFS= read -r f; do convert_doc "$f"; done

# ---------- 素材枚举 ----------
emit_media() { # $1=目录, $2=maxdepth
  find "$1" -maxdepth "$2" -type f \
    \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" \
       -o -iname "*.webp" -o -iname "*.bmp" -o -iname "*.mp4" -o -iname "*.webm" \
       -o -iname "*.ogg" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.m4v" \) \
    2>/dev/null | LC_ALL=C sort | while IFS= read -r f; do
    printf '"%s",' "$(printf '%s' "$f" | esc)"
  done
}

# style.txt 键值 -> JS 属性片段（白名单 + 数值校验）
style_props() { # $1=分区名, $2=允许键列表(空格分隔)
  local f="content/$1/style.txt" k v out="" keys=" $2 "
  [ -f "$f" ] || { printf ''; return; }
  while IFS='=' read -r k v; do
    case "$k" in ""|\#*) continue;; esac
    case "$keys" in *" $k "*) ;; *) continue;; esac
    [ -n "$v" ] || continue
    case "$k" in
      SIZE|SPEED|LINESPACING|PADDING|MARGIN|RADIUS|GROUPCOLS|REFRESH)
        case "$v" in *[!0-9.]*) continue;; esac;;
      TARGET)
        case "$v" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*) ;; *) continue;; esac;;
      COUNTUP)
        case "$v" in 1|yes|true) v=true;; *) v=false;; esac;;
    esac
    case "$k" in
      COUNTUP) out="$out,countup:$v";;
      *) out="$out,$(printf '%s' "$k" | tr 'A-Z' 'a-z'):\"$(printf '%s' "$v" | esc)\"";;
    esac
  done < "$f"
  printf '%s' "$out"
}

# 分区级视觉/布局键（对所有窗口类型有效，放进 zone 对象本体）
ZONE_KEYS="PADDING MARGIN ALIGNV RADIUS CARD GRADIENT SHADOW STROKE TABNUM ICON DECOR GROUP GROUPCOLS"

# ---------- 分区条目生成 ----------
emit_zone() { # 参数: name zx zy zw zh zdur ztype
  local name="$1" zx="$2" zy="$3" zw="$4" zh="$5" zdur="$6" ztype="$7"
  local nesc props zprops tf content
  nesc="$(printf '%s' "$name" | esc)"
  zprops="$(style_props "$name" "$ZONE_KEYS")"
  case "$ztype" in
    文本|text)
      tf="content/$name/text.txt"
      content=""
      [ -f "$tf" ] && content="$(escape_text < "$tf")"
      props="$(style_props "$name" "FONT SIZE COLOR BGCOLOR BOLD ITALIC ALIGN EFFECT SPEED LINESPACING")"
      printf '{name:"%s",x:%s,y:%s,w:%s,h:%s%s,text:{content:"%s"%s}}' \
        "$nesc" "$zx" "$zy" "$zw" "$zh" "$zprops" "$content" "$props"
      ;;
    时钟|clock)
      props="$(style_props "$name" "FORMAT MODE FONT SIZE COLOR BGCOLOR")"
      printf '{name:"%s",x:%s,y:%s,w:%s,h:%s%s,clock:{%s}}' \
        "$nesc" "$zx" "$zy" "$zw" "$zh" "$zprops" "${props#,}"
      ;;
    计时|timer)
      props="$(style_props "$name" "TARGET TITLE FONT SIZE COLOR BGCOLOR COUNTUP")"
      printf '{name:"%s",x:%s,y:%s,w:%s,h:%s%s,countdown:{%s}}' \
        "$nesc" "$zx" "$zy" "$zw" "$zh" "$zprops" "${props#,}"
      ;;
    二维码|qr)
      tf="content/$name/text.txt"
      content=""
      [ -f "$tf" ] && content="$(tr -d '\r' < "$tf" | awk '{printf "%s\\n", $0}' | sed 's/\\n$//; s/\\/\\\\/g; s/"/\\"/g')"
      props="$(style_props "$name" "COLOR BGCOLOR TITLE ECL")"
      printf '{name:"%s",x:%s,y:%s,w:%s,h:%s%s,qr:{content:"%s"%s}}' \
        "$nesc" "$zx" "$zy" "$zw" "$zh" "$zprops" "$content" "$props"
      ;;
    公告|notice)
      tf="content/$name/text.txt"
      content=""
      [ -f "$tf" ] && content="$(escape_text < "$tf")"
      props="$(style_props "$name" "TITLE COLOR BGCOLOR SIZE FONT ICON SPEED DATASRC REFRESH")"
      printf '{name:"%s",x:%s,y:%s,w:%s,h:%s%s,notice:{content:"%s"%s}}' \
        "$nesc" "$zx" "$zy" "$zw" "$zh" "$zprops" "$content" "$props"
      ;;
    *)
      printf '{name:"%s",x:%s,y:%s,w:%s,h:%s%s,duration:%s,slides:[' \
        "$nesc" "$zx" "$zy" "$zw" "$zh" "$zprops" "$zdur"
      emit_media "content/$name" 3
      printf ']}'
      ;;
  esac
}

# ---------- 生成 playlist.js + fonts.json ----------
TICKER_TEXT=""
[ -f ticker.txt ] && TICKER_TEXT="$(escape_text < ticker.txt)"
NOTIFY_TEXT=""
[ -f notify.txt ] && NOTIFY_TEXT="$(tr '\r' ' ' < notify.txt | tr '\n' ' ' | esc)"

PAGE_ZONES=""
PAGE_DUR="$PAGE_DURATION"
flush_page() {
  [ -n "$PAGE_ZONES" ] || return 0
  printf '{duration:%s,zones:[\n%s\n]},\n' "$PAGE_DUR" "$PAGE_ZONES"
  PAGE_ZONES=""
  PAGE_DUR="$PAGE_DURATION"
}

{
  echo "window.PLAYLIST={"
  echo "duration:$DURATION,"
  echo "sound:$SOUND_JS,"
  echo "reloadMinutes:$RELOAD_MINUTES,"
  echo "fill:\"$FILL\","
  echo "transition:\"$TRANSITION\","
  echo "transitionTime:$TRANSITION_TIME,"
  echo "twinkle:$TWINKLE_JS,"
  echo "perf:\"$PERF\","
  echo "kenburns:$KENBURNS_JS,"
  [ -n "$BGIMAGE" ] && echo "bgimage:\"$(printf '%s' "$BGIMAGE" | esc)\","
  [ -n "$BGCOLOR" ] && echo "bgcolor:\"$(printf '%s' "$BGCOLOR" | esc)\","
  [ -n "$BGMUSIC" ] && echo "bgmusic:\"$(printf '%s' "$BGMUSIC" | esc)\",bgmusicVol:$BGMUSIC_VOL,"
  [ -n "$SCREEN_OFF" ] && echo "screenOff:\"$SCREEN_OFF\","
  [ -n "$NOTIFY_TEXT" ] && printf 'notify:{text:"%s",minutes:%s},\n' "$NOTIFY_TEXT" "$NOTIFY_MINUTES"
  printf 'ticker:{text:"%s",effect:"%s",speed:%s,size:%s,color:"%s",bgcolor:"%s",bold:%s,height:%s,sep:"%s",mask:%s' \
    "$TICKER_TEXT" "$TICKER_EFFECT" "$TICKER_SPEED" "$TICKER_SIZE" \
    "$(printf '%s' "$TICKER_COLOR" | esc)" "$(printf '%s' "$TICKER_BGCOLOR" | esc)" \
    "$TICKER_BOLD_JS" "$TICKER_HEIGHT" "$(printf '%s' "$TICKER_SEP" | esc)" "$TICKER_MASK_JS"
  [ -n "$TICKER_FONT" ] && printf ',font:"%s"' "$(printf '%s' "$TICKER_FONT" | esc)"
  echo "},"
  # 字体包
  printf 'fontfaces:['
  found_font=""
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    found_font="1"
    fam="$(basename "${f%.*}")"
    case "${f##*.}" in
      ttf|TTF) fmt=truetype;;
      otf|OTF) fmt=opentype;;
      *) fmt=woff;;
    esac
    printf '{family:"%s",url:"%s",format:"%s"},' \
      "$(printf '%s' "$fam" | esc)" "$(printf '%s' "$f" | esc)" "$fmt"
  done <<EOF
$(find fonts -maxdepth 1 -type f \( -iname "*.ttf" -o -iname "*.otf" -o -iname "*.woff" \) 2>/dev/null | LC_ALL=C sort)
EOF
  echo "],"
  # 多节目页
  echo "pages:["
  if [ -f layout.txt ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      line="$(printf '%s' "$line" | tr -d '\r')"
      case "$line" in ""|\#*) continue;; esac
      # 页分隔符: --- 或 --- 秒数
      case "$line" in
        ---*)
          flush_page
          PAGE_DUR="${line#---}"
          PAGE_DUR="$(printf '%s' "$PAGE_DUR" | tr -d ' ')"
          case "$PAGE_DUR" in *[!0-9.]*) PAGE_DUR="$PAGE_DURATION";; ""|0|0.*) PAGE_DUR="$PAGE_DURATION";; esac
          continue;;
      esac
      case "$line" in *=*) ;; *) echo "[布局] 跳过非法行: $line"; continue;; esac
      name="$(printf '%s' "${line%%=*}" | tr -d ' ')"
      rest="$(printf '%s' "${line#*=}" | tr -d ' ')"
      zx=""; zy=""; zw=""; zh=""; zdur=""; ztype=""
      # 栅格语法: 名称=g:行,列,跨行,跨列[,秒][,类型]  （12x12 栅格）
      case "$rest" in
        g:*)
          g="${rest#g:}"
          gr="$(printf '%s' "$g" | cut -d, -f1)"
          gc="$(printf '%s' "$g" | cut -d, -f2)"
          grs="$(printf '%s' "$g" | cut -d, -f3)"
          gcs="$(printf '%s' "$g" | cut -d, -f4)"
          # 只校验前 4 个栅格字段（第 5/6 字段是秒数与类型名，允许中文/空）
          gbad=0
          case "$gr" in ""|*[!0-9]*) gbad=1;; esac
          case "$gc" in ""|*[!0-9]*) gbad=1;; esac
          [ -n "$grs" ] && case "$grs" in *[!0-9]*) gbad=1;; esac
          [ -n "$gcs" ] && case "$gcs" in *[!0-9]*) gbad=1;; esac
          [ "$gbad" = "1" ] && { echo "[布局] 跳过非法栅格行: $line"; continue; }
          [ -z "$grs" ] && grs=1
          [ -z "$gcs" ] && gcs=1
          [ "$gr" -ge 1 ] 2>/dev/null && [ "$gr" -le 12 ] || { echo "[布局] 栅格行号越界(1-12): $line"; continue; }
          [ "$gc" -ge 1 ] 2>/dev/null && [ "$gc" -le 12 ] || { echo "[布局] 栅格列号越界(1-12): $line"; continue; }
          zdur="$(printf '%s' "$g" | cut -d, -f5)"
          ztype="$(printf '%s' "$g" | cut -d, -f6)"
          # 换算为百分比（12 列 x 12 行）
          zy="$(awk -v r="$gr" 'BEGIN{printf "%.2f", (r-1)*100/12}')"
          zx="$(awk -v c="$gc" 'BEGIN{printf "%.2f", (c-1)*100/12}')"
          zh="$(awk -v n="$grs" 'BEGIN{printf "%.2f", n*100/12}')"
          zw="$(awk -v n="$gcs" 'BEGIN{printf "%.2f", n*100/12}')"
          ;;
        *)
          IFS=',' read -r zx zy zw zh zdur ztype <<EOF
$rest
EOF
          case "$zx$zy$zw$zh" in *[!0-9.]*) echo "[布局] 跳过非法行: $line"; continue;; esac
          ;;
      esac
      zdur="${zdur:-$DURATION}"
      case "$zdur" in *[!0-9.]*) zdur="$DURATION";; ""|.) zdur="$DURATION";; esac
      # 窗口类型: 第6字段显式指定优先; 否则按名称关键词自动推断; 兜底=文件
      case "$ztype" in
        文本|text|多行文本|单行文本) ztype="文本";;
        时钟|clock) ztype="时钟";;
        计时|timer|倒计时|countdown) ztype="计时";;
        二维码|qr) ztype="二维码";;
        公告|notice) ztype="公告";;
        文件|file|video|"") ztype="${ztype:-}"
          if [ -z "$ztype" ]; then
            case "$name" in
              *时钟*) ztype="时钟";;
              *计时*|*倒计时*) ztype="计时";;
              *二维码*|*扫码*) ztype="二维码";;
              *公告*) ztype="公告";;
              *文本*|*文字*|*通知*) ztype="文本";;
              *) ztype="文件";;
            esac
          fi;;
      esac
      frag="$(emit_zone "$name" "$zx" "$zy" "$zw" "$zh" "$zdur" "$ztype")"
      PAGE_ZONES="$PAGE_ZONES$frag,
"
    done < layout.txt
  fi
  flush_page
  echo "],"
  echo "slides:["
  emit_media content 1
  echo "]"
  echo "};"
} > playlist.js
echo "[MediaBoard] playlist.js 已生成"

# fonts.json（编辑器字体下拉用）
{
  printf '{"fonts":['
  first=1
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    fam="$(basename "${f%.*}")"
    [ $first -eq 0 ] && printf ','
    first=0
    printf '"%s"' "$(printf '%s' "$fam" | esc)"
  done <<EOF
$(find fonts -maxdepth 1 -type f \( -iname "*.ttf" -o -iname "*.otf" -o -iname "*.woff" \) 2>/dev/null | LC_ALL=C sort)
EOF
  printf ']}'
} > fonts.json
echo "[MediaBoard] fonts.json 已生成"

# ---------- 测试模式 ----------
[ "${MEDIABOARD_TEST:-0}" = "1" ] && exit 0

# ---------- 找浏览器 ----------
CHROME=""
for c in chromium-browser chromium google-chrome; do
  command -v "$c" >/dev/null 2>&1 && CHROME="$c" && break
done
if [ -z "$CHROME" ]; then
  echo "[错误] 找不到 chromium 浏览器，无法播放"; exit 1
fi
command -v xset >/dev/null 2>&1 && { xset s off 2>/dev/null; xset -dpms 2>/dev/null; }

# ---------- 看门狗循环 ----------
echo "[MediaBoard] 启动 $CHROME 全屏播放 (Ctrl+C 停止)"
echo "[MediaBoard] 配置编辑器: file://$DIR/editor.html   自检: file://$DIR/player.html?selftest=1"
while true; do
  "$CHROME" --kiosk --noerrdialogs --disable-infobars \
    --no-first-run --no-default-browser-check \
    --allow-file-access-from-files \
    --disable-features=Translate,TranslateUI,TranslateNewUX \
    --disable-session-crashed-bubble --disable-restore-session-state \
    --disable-background-networking --disable-component-update \
    --force-device-scale-factor=1 --lang=zh-CN \
    --autoplay-policy=no-user-gesture-required \
    "file://$DIR/player.html" >/dev/null 2>&1
  sleep 3
done
