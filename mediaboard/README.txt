MediaBoard 离线多媒体播放板（麒麟V10 ARM64 专用 · 分区版）
==============================================================

零依赖：只用系统自带的 chromium 浏览器，不联网、不装任何软件。

【安装】（U盘拷过来后执行一次）
  tar xzf mediaboard-kylin-arm64.tar.gz
  cd mediaboard
  bash install.sh

【最简单的用法（全屏轮播）】
  图片/视频 -> 拷进 content/ 目录，按文件名顺序播放（建议 01-xxx.jpg 02-yyy.mp4）
  滚动字幕  -> 编辑 ticker.txt

【分屏自由组合（仿 LEDvision 节目窗口）】
  1. 编辑 layout.txt，每行一个窗口：
       名称=起点X,起点Y,宽,高[,图片停留秒数]
     数字都是占屏幕的百分比（按整块屏幕算，左上角是 0,0）。例如：
       主画面=0,0,70,86        左侧 70% 宽、86% 高
       侧栏=70,0,30,56         右上 30%，图片 5 秒一切换
       时钟=70,56,30,30        右下放实时时钟
  2. 在 content/ 下建同名目录放素材：
       content/主画面/01-宣传.jpg  02-视频.mp4
       content/侧栏/01-海报.jpg
  3. 各窗口同时独立播放，互不影响；底部滚动字幕条自动保留。

  提示：底部字幕条固定占屏幕下方 9%。分区高度建议不超过 91，否则会被字幕条压住。

【PPT 播放】
  直接放 content/（或对应分区目录）里，启动时自动转图片
  （需机器装有 WPS 或 LibreOffice）；若转换失败，请在电脑上把
  PPT 另存为图片（WPS：文件->另存为->输出为图片）再拷入。

【设置】编辑 settings.txt（改完执行 bash stop.sh 再 bash start.sh 生效）：
  DURATION=10        图片停留秒数（分区里可单独覆盖）
  SOUND=no           视频声音 yes/no
  RELOAD_MINUTES=30  每隔多少分钟自动刷新（换新内容后最多等这么久生效）
  TICKER_SPEED=60    字幕滚动速度，单位约 = 像素/秒，数值越大越快
  TICKER_COLOR=#ffff00   字幕颜色
  TICKER_BGCOLOR=#1a3a6b 字幕底色
  FILL=contain       画面填充方式：
                       contain = 完整显示，比例不符时留黑边（不裁切，默认）
                       cover   = 铺满分区，超出部分裁掉（无黑边）

【启动/停止】
  手动启动: bash start.sh
  停止:     bash stop.sh
  开机自动播放（install.sh 已设置）

【布局校准（可选）】
  想确认分区实际落在屏幕的哪个位置，用这个地址打开播放器：
     chromium --kiosk "file:///<安装路径>/mediaboard/player.html?diag=1"
  画面左上角会打印一行绿字，例如：
     viewport=1280x720 dpr=1 | 主画面=0,0,896x619 | 侧栏=896,0,384x403 | 时钟=896,403,384x216
  里面就是浏览器视口尺寸和每个分区的真实像素矩形，可直接对照 layout.txt 核对。

【支持格式】
  图片: jpg jpeg png gif webp bmp
  视频: mp4(H.264) webm ogg mov mkv（若黑屏/无声请转成 H.264 编码的 mp4）

【问题排查】
  黑屏无内容: content/ 为空，或 layout.txt 里分区名和 content/ 下目录名不一致
  某分区黑:   该分区目录里没有图片/视频
  画面有黑边: 素材比例和分区比例不一致，把 FILL 改成 cover，或按分区像素做素材
  视频不播:   编码不兼容，转成 H.264 mp4
  字幕不动:   ticker.txt 为空
  字幕太慢/太快: 调 settings.txt 里的 TICKER_SPEED
