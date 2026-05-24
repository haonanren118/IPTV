#!/bin/bash
# Cloudflare Pages 自动部署脚本
# 使用方法: ./deploy-cf-pages.sh

echo "🚀 IPTV Manager - Cloudflare Pages 部署脚本"
echo "============================================"
echo ""

# 检查 wrangler 是否安装
if ! command -v wrangler &> /dev/null; then
    echo "❌ 未检测到 Wrangler CLI"
    echo "正在安装..."
    npm install -g wrangler
fi

# 登录检查
echo "🔑 检查 Cloudflare 登录状态..."
wrangler whoami
if [ $? -ne 0 ]; then
    echo "请先登录:"
    wrangler login
fi

echo ""
echo "📋 部署步骤:"
echo "1. 创建 KV 命名空间"
echo "2. 部署到 Pages"
echo ""

# 创建 KV 命名空间
echo "📝 创建 KV 命名空间..."
KV_OUTPUT=$(wrangler kv:namespace create "IPTV_CACHE" 2>&1)
echo "$KV_OUTPUT"

# 提取 KV ID
KV_ID=$(echo "$KV_OUTPUT" | grep -oP 'id = "\K[^"]+')

if [ -n "$KV_ID" ]; then
    echo "✅ KV 命名空间创建成功: $KV_ID"
    
    # 更新 wrangler.toml
    echo "📝 更新配置文件..."
    cat > wrangler.toml << EOF
name = "iptv"
compatibility_date = "2024-12-01"

[[kv_namespaces]]
binding = "IPTV_CACHE"
id = "$KV_ID"
EOF
    echo "✅ 配置文件已更新"
else
    echo "⚠️ KV 命名空间可能已存在，尝试获取现有 ID..."
    wrangler kv:namespace list
fi

echo ""
echo "🚀 部署到 Cloudflare Pages..."
echo "注意: 首次部署需要在 Dashboard 中关联 Git 仓库"
echo ""
echo "请在浏览器中完成以下操作:"
echo "1. 访问: https://dash.cloudflare.com/c80878b678daf3e3f69dd0950bd5f4f8/pages/view/iptv"
echo "2. 进入 Settings → Functions → KV namespace bindings"
echo "3. 添加绑定: Variable name = IPTV_CACHE"
echo "4. 选择 KV namespace: IPTV_CACHE"
echo "5. Save 并重新部署"
echo ""
echo "✅ 脚本执行完成!"
