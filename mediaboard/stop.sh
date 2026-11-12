#!/usr/bin/env bash
# 停止 MediaBoard 播放
pkill -f "mediaboard/player.html" 2>/dev/null && echo "已停止播放" || echo "没有在播放"
