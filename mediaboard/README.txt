MediaBoard 离线多媒体播放板（麒麟V10 ARM64 专用）
=================================================

零依赖：只用系统自带的 chromium 浏览器，不联网、不装任何软件。

【安装】（U盘拷过来后执行一次）
  tar xzf mediaboard-kylin-arm64.tar.gz
  cd mediaboard
  bash install.sh

【放内容】
  图片/视频 -> 拷进 content/ 目录，按文件名顺序播放（建议起名 01-xxx.jpg 02-yyy.mp4）
  滚动字幕  -> 编辑 ticker.txt
  PPT       -> 直接放 content/ 里，启动时自动转图片（需机器装有 WPS 或 LibreOffice）；
               若转换失败，请在电脑上把 PPT 另存为图片（WPS：文件->另存为->输出为图片）
               再拷进 content/。

【设置】编辑 settings.txt：
  DURATION=10        每张图片停留秒数
  SOUND=yes          视频声音 yes/no
  RELOAD_MINUTES=30  每隔多少分钟自动刷新（换新内容后最多等这么久生效）
  TICKER_SPEED=60    字幕速度，数值越大越慢
  TICKER_COLOR=#ffff00   字幕颜色
  TICKER_BGCOLOR=rgba(0,0,0,0.72)  字幕底色

【启动/停止】
  手动启动: bash start.sh
  停止:     bash stop.sh
  开机自动播放（install.sh 已设置）
  播放中按键盘 ← → 可手动切换上一张/下一张

【支持格式】
  图片: jpg jpeg png gif webp bmp
  视频: mp4(H.264) webm ogg mov mkv（若黑屏/无声请转成 H.264 编码的 mp4）

【问题排查】
  启动后黑屏无内容: content/ 为空，或文件名带特殊字符
  视频不播: 编码不兼容，用格式工厂/ffmpeg 转 H.264 mp4
  字幕不动: ticker.txt 为空
