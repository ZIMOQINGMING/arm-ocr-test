MediaBoard v3 离线多媒体看板（麒麟V10 ARM64 · LEDvision 全功能 + 视觉增强版）
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
  「--- N」单独一行 = 另起一个节目页，N=该页停留秒；多页按顺序循环。
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
    ICON=horn        图标 info/warn/star/clock/horn/check/flag
    DECOR=line       装饰：line 顶部细线 / corner 四角角标
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

【滚动字幕 ticker.txt + settings.txt】
  ticker.txt 每行一段；settings.txt 里调效果/速度/字体/字号/颜色/底色/
  条高/分隔符/两端渐隐(TICKER_MASK)。

【视觉增强与性能档位 settings.txt】
  TRANSITION=fade|fade-zoom|blur-fade|slide-soft|cover-*|wipe-*|random|none
  TRANSITION_TIME=0.8   特效时长
  KENBURNS=yes          图片缓慢推近（静图变"活"）
  PERF=high|mid|low     high 全效果 / mid 去模糊与 KenBurns / low 只留淡入淡出
                        —— ARM64 软渲染卡顿时直接调低，效果与流畅解耦
  BGCOLOR / BGIMAGE / BGMUSIC / SCREEN_OFF(定时黑屏防烧屏) / TWINKLE

【字体选择】
  把 .ttf/.otf/.woff 丢进 fonts/，字体名=文件名（去扩展名），
  FONT=方正楷体 即可用；编辑器里的字体下拉会自动读 fonts.json。
  系统字体可用 fc-list :lang=zh 查（Noto Sans/Serif CJK 一般都有）。
  提示：完整中文字体 10MB+，建议用子集化字体（pyftsubset 可把 10MB 压到几百 KB）。

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
