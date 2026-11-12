MediaBoard v4 离线多媒体看板（麒麟V10 ARM64 · LEDvision 编排对齐 + 图层合成版）
====================================================================

零依赖：只用系统自带 chromium 浏览器，不联网、不装任何软件。
（qr.js 为包内自带的离线二维码生成库，MIT 协议，不需要安装。）

【安装】U盘拷过来后执行一次
  tar xzf mediaboard-kylin-arm64.tar.gz
  cd mediaboard
  bash install.sh

【三种使用方式，从易到难】
  A. 只想放图片/视频：素材丢进 content/，bash start.sh 就会全屏轮播。
  B. 想套现成版式：cp -r templates/企业信息发布/* .  然后改 content 下的文字。
  C. 想可视化调：用浏览器打开 editor.html（见下"可视化编辑器"）。

【可视化编辑器 editor.html（v3 新增，最大改动）】
  用系统 chromium 打开本机文件：
    chromium --app=file:///opt/mediaboard/editor.html
  左侧表单改参数，右侧实时预览（拖滑块立刻变），支持：
    · 全局：切换特效(16种含柔和型)、特效时长、性能档位、填充方式、Ken Burns、背景色
    · 节目页时间轴：加页/删页/前移后移/改每页停留秒
    · 分区：位置大小、内外距、垂直对齐、圆角、卡片投影、渐变底色、文字阴影/描边、
            图标、装饰线、字号字色、6 种窗口类型全部可视化编辑
    · 字幕条：内容/效果/速度/字号/条高/颜色/两端渐隐
    · 素材导入：选本机图片视频，立刻在预览里看到效果（仅预览用）
  【导出】点"导出配置包(ZIP)" → 得到 settings.txt / layout.txt / ticker.txt /
    各分区 content/<名字>/text.txt+style.txt / 素材清单.txt
    → 解压覆盖到安装目录 → bash stop.sh && bash start.sh
  草稿自动存本机浏览器，断电不丢；也能导入现有 layout.txt/settings.txt 改。

【真机自检（新机器到手先跑这个）】
  浏览器打开  file:///<安装路径>/mediaboard/player.html?selftest=1
  屏上大字列出每项能力：动画引擎 / clip-path / 模糊 / 遮罩渐隐 / 等宽数字 /
  渐变 / 投影 / 描边 / canvas / 二维码库 / 本地存储 / H.264 / MP3 / 字体包加载
  全绿=这台机器能跑全部效果；有红项=对应效果会自动降级，不影响播放。
  拍照留档即可作为兼容性证据。

【布局 layout.txt】
  每行一个窗口，两种写法（可混用）：
    ① 百分比：名称=X,Y,宽,高[,素材停留秒][,窗口类型]
    ② 栅格：  名称=g:行,列,跨行,跨列[,秒][,类型]     —— 12×12 栅格，对齐更省心
      例：主画面=g:1,1,8,7  → 第1行第1列起，占8行7列
  「--- N」单独一行 = 结束上一页并另起一页，N 是【上一页】的停留秒数；
  多页按顺序循环。最后一页的时长用 PAGE_DURATION（settings.txt）。
  窗口类型：文件(默认) / 文本 / 时钟 / 计时 / 二维码 / 公告
  不写类型时按名字猜：含"时钟"→时钟，含"公告"→公告，含"二维码/扫码"→二维码…

【分区样式 style.txt】（content/分区名/style.txt，k=v 每行一条，均可选）
  —— 通用（六种窗口都能用）——
    PADDING=2        内边距 vh（留白一控，立刻不"简陋"）
    MARGIN=1         外边距 %（分区四周留缝，卡片感）
    ALIGNV=middle    垂直对齐 top/middle/bottom
    RADIUS=1         圆角 vh；CARD=yes 卡片模式（圆角+投影）
    GRADIENT=#0b1e3d,#1a3a6b   135°渐变底色
    SHADOW=yes       文字阴影（大屏远距离可读性）
    STROKE=yes       白字黑描边（浅底上尤其需要）
    TABNUM=yes       等宽数字（时钟跳动不抖）
    ICON=horn        图标 29 种：info/warn/star/clock/horn/check/flag/arrowR/arrowL/
                     arrowUp/arrowDown/calendar/user/phone/mail/pin/chart/gear/sun/moon/
                     cloud/battery/wifi/heart/shield/fire/doc/speaker/play
    DECOR=line       装饰：line 顶部细线 / corner 四角角标
    —— v4 合成与特效（对齐 LEDvision 的窗口层次/分块特效）——
    LAYER=1          图层：1 最上层，数字越大越靠后；不写=按 layout 书写顺序叠放
    OPACITY=70       分区透明度 0-100（做"背景视频 + 半透明信息卡"必须两项一起用）
    EDGE_MASK=6      四边渐隐 %，让分区融进背景（柔和边缘，不写=不要）
    GRID_FX=4|9|16   分块特效：静态内容分 4/9/16 块错峰入场；
                     视频/多图轮播分区自动整窗降级（软渲染不硬扛）
  —— 文本窗 ——
    FONT=字体名 SIZE=6 COLOR=#00ff00 BGCOLOR=#222222 BOLD=yes ITALIC=no
    ALIGN=center LINESPACING=1.5
    EFFECT=static|scroll-left|scroll-up|blink|typewriter   SPEED=60
  —— 时钟窗 ——
    FORMAT=datetime|date|time|week|weektime（也可自定义 {Y}{M}{D}{h}{m}{s}{W}）
    MODE=dial 表盘指针样式（默认 digital 数字）
  —— 计时窗 ——
    TARGET=2027-01-01 09:00（不写=从开机正计时） TITLE=距开幕还有
  —— 二维码窗 ——
    content/分区名/text.txt 里写要编码的文字/网址（支持中文），
    TITLE=扫码报修  COLOR=#111111  BGCOLOR=#ffffff  ECL=M(L/M/Q/H 纠错级别)
  —— 公告列表窗 ——
    content/分区名/text.txt 每行一条；行多会自动上滚
    TITLE=今日通知  ICON=horn  SIZE=3.2  SPEED=30
    DATASRC=data/值班.json  REFRESH=10   （可选：本地JSON每10分钟刷一次，
       json 格式 {"items":["第一条","第二条"]}）
  —— 文件窗 ——
    GROUP=grid  GROUPCOLS=2   九宫格：分区内多图一次铺开（默认轮播）

【播放规则：页级有效期与次数（v4）】
  layout.txt 里，在 --- 之后、该页分区之前加：
    @PLAYS=3                      这一页播 3 次后跳过（不写=一直循环）
    @VALID=2026-01-01~2026-12-31  只在有效期播，过期自动跳过
  所有页都播完（次数用尽）会自动清零重新轮，不会停在最后一页。

【定时指令表 schedule.txt（v4）】
  每行 HH:MM=指令，按本机时钟执行，同一分钟只执行一次：
    play:2        跳到第 2 页        pause/resume   暂停/恢复自动换页
    screenoff     全屏黑            screenon       取消黑屏
  只做播放器内部动作，不重启、不关机（浏览器权限边界）。样例见 schedule.txt。

【滚动字幕 ticker.txt + settings.txt】
  ticker.txt 每行一段；settings.txt 里调效果/速度/字体/字号/颜色/底色/
  条高/分隔符/两端渐隐(TICKER_MASK)。
  v4 起字幕可以当"叠加层"用（视频全屏也能压字）：
    TICKER_OVERLAY=yes   浮在所有分区之上，不占布局（默认）
    TICKER_OVERLAY=no    舞台自动给字幕让位，分区不被压住
    TICKER_POS=top|bottom 字幕在顶还是底

【视觉增强与性能档位 settings.txt】
  TRANSITION=fade|fade-zoom|blur-fade|slide-soft|flip-3d|depth-zoom|cover-*|wipe-*|random|none
                        flip-3d=卡片翻转感 depth-zoom=从深处推出（3D 观感，非真 3D）
  TRANSITION_TIME=0.8   特效时长
  KENBURNS=yes          图片缓慢推近（静图变"活"）
  PERF=high|mid|low     high 全效果 / mid 去模糊与 KenBurns / low 只留淡入淡出
                        —— ARM64 软渲染卡顿时直接调低，效果与流畅解耦
  BGCOLOR / BGIMAGE / BGMUSIC / SCREEN_OFF(定时黑屏防烧屏) / TWINKLE

【字体包（v4 已内置 3 款子集字体，共 6.5MB）】
  fonts/ 里现成可用，style.txt 直接写中文名：
    FONT=思源黑体 常规   /  FONT=思源黑体 粗   /  FONT=思源宋体 粗
  子集范围：GB2312 常用字 + 英文数字标点（7545 字），正文/标题都够；生僻字会回落到系统字体。
  显示名映射写在 fonts/FONTS.txt（"文件名=显示名"），想改成别的名字改这里即可。
  自己加字体：.ttf/.otf/.woff/.woff2 丢进 fonts/，名字默认=文件名（去扩展名）。
  完整中文字库 10MB+ 在 ARM64 离网机上加载慢，务必用子集：pyftsubset 一条命令压到 1/8。

【纹理素材（v4 内置 6 张，程序化生成、无版权风险）】
  textures/ 里：brushed 金属拉丝 / grid 细网格 / carbon 碳纤维 / noise 细颗粒 /
                beams 斜向光带 / vignette 中心提亮
  用法：settings.txt 写  BGIMAGE=textures/vignette.png
  也可以拷进某个分区当图片素材用。尺寸 1280x720，任何分辨率都能铺满。
  注意：真实拍摄的 4K 动态背景视频请自行准备（离网机别同时解码多条视频）。

【PPT/Word/Excel】
  直接放进 content/（或分区目录），启动时自动转图（需 WPS 或 LibreOffice）；
  转不了就在电脑上另存为图片再拷入。

【启动/停止/校准】
  bash start.sh            开始播放（install.sh 已设开机自启）
  bash stop.sh             停止
  player.html?diag=1       左上角绿字显示视口与分区真实像素矩形（对位用）
  player.html?selftest=1   能力自检

【支持格式】
  图片 jpg/jpeg/png/gif/webp/bmp    视频 mp4(H.264)/webm/ogg/mov/mkv

【排查】
  黑屏无内容     content/ 空，或 layout 里分区名与 content/ 目录名不一致
  文本窗不显示   content/分区名/text.txt 缺失或为空
  字体不生效     文件在 fonts/？FONT 名与文件名一致（不含扩展名）？
  画面有黑边     素材比例≠分区比例：FILL=cover，或按分区像素做素材
  视频不播       编码不兼容，转 H.264 mp4
  效果卡顿       PERF 调 mid 或 low
  二维码空白     该分区 text.txt 为空；或内容过长（缩短文字）
  编辑器预览白屏 用 chromium 打开（--allow-file-access-from-files 才行）
