#!/bin/sh
# IPTV 容器统一入口：同时运行三个服务
# 1. app.py (5000) - 公网源扫描+测速+生成播放列表
# 2. web_admin.py (9998) - Web管理界面 + 触发本地源上传
# 3. upload_and_deploy.py (后台循环) - 本地IPTV源定时上传CF KV

set -e

echo "=========================================="
echo "  IPTV 容器启动 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 启动公网源扫描服务（app.py，端口 5000）
echo "[1/3] 启动公网源扫描服务 (app.py:5000) ..."
python /app/app.py &
APP_PID=$!
echo "  → app.py PID: $APP_PID"

# 等待 app.py 初始化完成（避免和 web_admin 抢资源）
sleep 3

# 启动本地源上传循环（upload_and_deploy.py）
echo "[2/3] 启动本地源上传服务 (upload_and_deploy.py) ..."
python /app/upload_and_deploy.py &
UPLOAD_PID=$!
echo "  → upload_and_deploy.py PID: $UPLOAD_PID"

# 启动 Web 管理界面（web_admin.py，端口 9998）— 前台运行保持容器存活
echo "[3/3] 启动 Web 管理界面 (web_admin.py:9998) ..."
echo ""
echo "✅ 所有服务已启动："
echo "   • 公网源扫描:    http://0.0.0.0:5000  (/iptv, /txt, /forceRetest)"
echo "   • 本地源上传:    后台运行 (每6小时自动上传到 CF KV)"
echo "   • Web管理界面:   http://0.0.0.0:9998"
echo ""

# 前台运行 web_admin.py（容器主进程）
exec python /app/web_admin.py

# 清理子进程
echo "收到退出信号，清理子进程..."
kill $APP_PID $UPLOAD_PID 2>/dev/null || true
wait $APP_PID $UPLOAD_PID 2>/dev/null || true
echo "容器已停止"
