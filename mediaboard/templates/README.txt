MediaBoard v3 主题模板（六套）
=====================================
用法（在 mediaboard 安装目录里执行，覆盖现有配置）：

  cp -r templates/企业信息发布/* .
  bash stop.sh && bash start.sh

每套模板包含:
  layout.txt      分区布局（12x12 栅格语法）
  settings.txt    配色/特效/字幕/性能档位
  ticker.txt      底部滚动字幕
  content/<分区>/ text.txt（要改的文字都在这里） + style.txt（字体颜色等）

改文字就改 content 下各分区的 text.txt，不用动 style。
主画面（文件窗）没有自带图片，把你的图片/视频放进 content/主画面/ 即可。
用了 DATASRC 的模板（交通值班）需把 data/值班.json 一起拷过去。

字体说明: 模板里写的 Noto Serif CJK SC 等系统字体，若目标机没装会自动回落
到默认黑体，不影响显示；要精确字体就把 ttf 放进 fonts/ 并在 style 里改 FONT。
