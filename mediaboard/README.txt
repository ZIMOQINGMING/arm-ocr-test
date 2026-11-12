MediaBoard v2 离线多媒体看板（麒麟V10 ARM64 · LEDvision 风格全功能版）
====================================================================

零依赖：只用系统自带的 chromium 浏览器，不联网、不装任何软件。

【安装】（U盘拷过来后执行一次）
  tar xzf mediaboard-kylin-arm64.tar.gz
  cd mediaboard
  bash install.sh

【最简单的用法（全屏轮播）】
  图片/视频 -> 拷进 content/ 目录，按文件名顺序播放（建议 01-xxx.jpg 02-yyy.mp4）
  滚动字幕  -> 编辑 ticker.txt

【分屏自由组合 + 多节目页（仿 LEDvision）】
  1. 编辑 layout.txt，每行一个窗口：
       名称=起点X,起点Y,宽,高[,图片停留秒数][,窗口类型]
     数字都是占屏幕的百分比。窗口类型四种：
       文件  图片/视频轮播（默认，素材放 content/同名目录/）
       文本  多行文字窗（内容在 content/同名目录/text.txt，样式在同目录 style.txt）
       时钟  实时时钟（样式在 content/同名目录/style.txt，可数字可表盘）
       计时  倒计时/正计时（style.txt 里写 TARGET=2027-01-01 09:00）
     例如：
       主画面=0,0,70,86
       通知=70,0,30,28,10,文本
       时钟=70,28,30,29,10,时钟
       倒计时=70,57,30,29,10,计时
  2. 「--- 45」单独一行 = 另起一个节目页（45=该页停留秒数），页按顺序循环；
     单页时写不写 --- 都一样。
  3. 各窗口同时独立播放；底部滚动字幕条自动保留（字幕条高度 TICKER_HEIGHT）。

【文本窗样式 style.txt】（content/分区名/style.txt，k=v 每行一条，均可选）
  FONT=字体名        用 fonts/ 里装的字体名，或系统字体
  SIZE=6             字号（vh，占屏高百分比数字，1~15 合理）
  COLOR=#00ff00      文字颜色
  BGCOLOR=#222222    窗口底色（支持 #rrggbb 或 rgba(0,0,0,0.5)）
  BOLD=yes ITALIC=no 加粗/斜体
  ALIGN=center       对齐 left/center/right
  LINESPACING=1.5    行距倍数
  EFFECT=static      效果: static静止 / scroll-left左移 / scroll-up上滚 /
                     blink闪烁 / typewriter打字机
  SPEED=60           滚动速度像素/秒（typewriter=每秒字数）

【时钟/计时窗样式 style.txt】
  时钟: FORMAT=datetime  datetime=日期+时间 / time=仅时间 / date=仅日期 /
                       week=日期+星期 / weektime=星期+时间（也可自定义写
                       {Y}{M}{D}{h}{m}{s}{W} 组合，如 {Y}年{M}月{D}日）
        MODE=dial       dial=表盘指针样式（默认 digital 数字）
        FONT/SIZE/COLOR/BGCOLOR 同文本窗
  计时: TARGET=2027-01-01 09:00   倒计时目标（无 TARGET = 从开机起正计时）
        TITLE=距开幕还有          标题行（可选）
        FONT/SIZE/COLOR/BGCOLOR 同上

【滚动字幕（ticker.txt + settings.txt）】
  ticker.txt 每行一段文字（scroll-up 效果时按行向上滚动）。
  settings.txt 里可调: 效果(scroll-left/scroll-up/blink/static/typewriter)、
  速度、字体、字号、颜色、底色、加粗、条高、循环分隔符。

【自定义字体包（字体选择的关键）】
  把 .ttf/.otf/.woff 字体文件放进 mediaboard/fonts/ 目录即可，
  字体名 = 文件名（去掉扩展名）。layout/style/settings 里的 FONT 直接写
  该名字，如 fonts/方正楷体.ttf -> FONT=方正楷体。
  系统已自带 Noto Sans CJK（黑体系）等中文字体，可用命令查看：
    fc-list :lang=zh
  注意：完整中文字体一个 10MB+，建议放精选/子集化字体。

【切换特效】settings.txt:
  TRANSITION=fade  素材切换特效（fade/random/cover-上下左右覆盖/
                   wipe-各方向擦除/none，详见 settings.txt 注释）
  TRANSITION_TIME=0.8  特效时长秒数
  TWINKLE=no       图片停留期闪烁

【背景 / 背景音乐 / 通知 / 定时关屏】settings.txt:
  BGIMAGE=bg/背景.jpg   全屏背景图（媒体分区之外可见）
  BGCOLOR=#000022       背景色
  BGMUSIC=bGM.mp3       背景音乐循环（BGMUSIC_VOL 音量 0~1）
  SCREEN_OFF=22:30-07:30 每天定时黑屏时段（防烧屏，跨零点也可）
  notify.txt 有内容时：顶部红色横幅插播 NOTIFY_MINUTES 分钟后消失

【PPT/Word/Excel 播放】
  直接放 content/（或对应分区目录）里，启动时自动转图片
  （需机器装有 WPS 或 LibreOffice）；若转换失败，请在电脑上把文档
  另存为图片再拷入。

【设置】全部在 settings.txt（改完执行 bash stop.sh 再 bash start.sh 生效）。

【启动/停止】
  手动启动: bash start.sh
  停止:     bash stop.sh
  开机自动播放（install.sh 已设置）

【布局校准（可选）】
  用地址 file:///<安装路径>/mediaboard/player.html?diag=1 打开，
  左上角绿字显示视口尺寸、当前节目页和每个分区的真实像素矩形。

【支持格式】
  图片: jpg jpeg png gif webp bmp
  视频: mp4(H.264) webm ogg mov mkv（若黑屏/无声请转成 H.264 编码的 mp4）

【问题排查】
  黑屏无内容: content/ 为空，或 layout.txt 里分区名和 content/ 下目录名不一致
  文本窗不显示: content/分区名/text.txt 缺失或为空
  自定义字体不生效: 确认文件在 fonts/ 目录、FONT 名与文件名一致（不含扩展名）
  画面有黑边: 素材比例和分区比例不一致，把 FILL 改成 cover，或按分区像素做素材
  视频不播:   编码不兼容，转成 H.264 mp4
  字幕不动:   ticker.txt 为空
  通知不消失: notify.txt 内容播完 NOTIFY_MINUTES 分钟自动消失，删掉 notify.txt 即可
