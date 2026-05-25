#!/bin/sh
# IPTV 容器统一入口：运行两个服务
# 1. upload_and_deploy.py (后台循环) - 本地IPTV源定时上传CF KV
# 2. web_admin.py (9998 前台) - Web管理界面 + 触发本地源上传

set -e

echo "=========================================="
echo "  IPTV 容器启动 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 启动本地源上传循环（upload_and_deploy.py）
echo "[1/2] 启动本地源上传服务 (upload_and_deploy.py) ..."
python3 /app/upload_and_deploy.py &
UPLOAD_PID=$!
echo "  → upload_and_deploy.py PID: $UPLOAD_PID"

# 启动 Web 管理界面（web_admin.py，端口 9998）— 前台运行保持容器存活
echo "[2/2] 启动 Web 管理界面 (web_admin.py:9998) ..."
echo ""
echo "✅ 所有服务已启动："
echo "   • 本地源上传:    后台运行 (每6小时自动上传到 CF KV)"
echo "   • Web管理界面:   http://0.0.0.0:9998"
echo ""

# 前台运行 web_admin.py（容器主进程）
exec python3 /app/web_admin.py

# 清理子进程
echo "收到退出信号，清理子进程..."
kill $UPLOAD_PID 2>/dev/null || true
wait $UPLOAD_PID 2>/dev/null || true
echo "容器已停止"
