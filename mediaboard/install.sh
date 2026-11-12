#!/usr/bin/env bash
# MediaBoard 安装脚本：复制到 ~/mediaboard，设置开机自启
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/mediaboard"

mkdir -p "$DEST"
cp -r "$SRC"/. "$DEST"/
chmod +x "$DEST"/start.sh "$DEST"/stop.sh

# 开机自启（UKUI/GNOME 通用 freedesktop 标准）
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/mediaboard.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MediaBoard
Comment=离线多媒体播放板
Exec=$DEST/start.sh
X-GNOME-Autostart-enabled=true
EOF

# 桌面快捷方式（双击启动）
DESKTOP_DIR="$HOME/桌面"
[ -d "$DESKTOP_DIR" ] || DESKTOP_DIR="$HOME/Desktop"
cat > "$DESKTOP_DIR/启动播放板.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=启动播放板
Exec=$DEST/start.sh
Terminal=true
EOF
chmod +x "$DESKTOP_DIR/启动播放板.desktop" 2>/dev/null || true

echo ""
echo "安装完成 -> $DEST"
echo "下一步:"
echo "  1. 把图片/视频拷进 $DEST/content/ （按文件名顺序播放）"
echo "  2. 想套现成版式: cp -r \"$DEST/templates/企业信息发布/\"* \"$DEST/\"  然后改 content 下的文字"
echo "  3. 想可视化调界面: chromium --app=file://$DEST/editor.html"
echo "  4. 真机能力自检:   chromium --app=file://$DEST/player.html?selftest=1"
echo "  5. 运行 bash $DEST/start.sh 开始播放（重启后自动播放）"
