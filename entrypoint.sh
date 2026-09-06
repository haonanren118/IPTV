#!/bin/sh
# IPTV 容器统一入口：运行两个服务
# 1. upload_and_deploy.py (后台循环) - 本地IPTV源定时上传CF KV
# 2. web_admin.py (9998 前台) - Web管理界面 + 触发本地源上传

set -e

echo "=========================================="
echo "  IPTV 容器启动 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 启动延迟：等待网络就绪（NAS 容器启动时网卡/DNS 可能尚未完全就绪）
STARTUP_DELAY=${STARTUP_DELAY:-30}
echo "[0/2] 启动延迟 ${STARTUP_DELAY}s，等待网络就绪..."
sleep "$STARTUP_DELAY"

# 启动本地源上传循环（upload_and_deploy.py）
# 修复：原脚本只在启动时跑一次，没有定时器导致永不再自动更新。
# 这里用 while + sleep 包成每 6 小时一次的循环。
UPLOAD_INTERVAL=${UPLOAD_INTERVAL:-21600}  # 默认 6 小时（秒）
echo "[1/2] 启动本地源上传服务 (upload_and_deploy.py)，每 ${UPLOAD_INTERVAL}s 自动循环..."
(
  while true; do
    echo "[loop $(date '+%Y-%m-%d %H:%M:%S')] 开始一次完整上传流程..."
    python3 /app/upload_and_deploy.py || echo "[loop] 本次上传失败，${UPLOAD_INTERVAL}s 后重试"
    echo "[loop] 本次完成，休眠 ${UPLOAD_INTERVAL}s..."
    sleep "$UPLOAD_INTERVAL"
  done
) &
UPLOAD_PID=$!
echo "  → 上传循环 PID: $UPLOAD_PID"

# 启动 Web 管理界面（web_admin.py，端口 9998）— 前台运行保持容器存活
echo "[2/2] 启动 Web 管理界面 (web_admin.py:9998) ..."
echo ""
echo "✅ 所有服务已启动："
echo "   • 本地源上传:    后台循环（每 ${UPLOAD_INTERVAL}s 自动上传到 CF KV）"
echo "   • Web管理界面:   http://0.0.0.0:9998"
echo ""

# 前台运行 web_admin.py（容器主进程）
exec python3 /app/web_admin.py

# 清理子进程
echo "收到退出信号，清理子进程..."
kill $UPLOAD_PID 2>/dev/null || true
wait $UPLOAD_PID 2>/dev/null || true
echo "容器已停止"
