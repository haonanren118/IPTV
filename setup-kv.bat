@echo off
chcp 65001 >nul
echo ===================================
echo IPTV KV 绑定工具
echo ===================================
echo.

set /p API_TOKEN=请输入 Cloudflare API Token: 
set ACCOUNT_ID=c80878b678daf3e3f69dd0950bd5f4f8

echo.
echo [1/3] 检查并创建 KV 命名空间...

curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/%ACCOUNT_ID%/storage/kv/namespaces" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  --data "{\"title\":\"IPTV_CACHE\"}" > kv_create.json

type kv_create.json | findstr "\"success\": true" >nul
if %errorlevel% == 0 (
    echo ✅ KV 命名空间创建成功
) else (
    echo ℹ️ KV 命名空间可能已存在，尝试获取 ID...
)

echo.
echo [2/3] 获取 KV 命名空间 ID...

curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/%ACCOUNT_ID%/storage/kv/namespaces" ^
  -H "Authorization: Bearer %API_TOKEN%" > kv_list.json

echo 请手动在 Cloudflare Dashboard 中绑定 KV：
echo.
echo 1. 访问 https://dash.cloudflare.com/%ACCOUNT_ID%/pages/view/iptv
echo 2. 点击 Settings → Functions
echo 3. 找到 KV namespace bindings → Add binding
echo 4. Variable name: IPTV_CACHE
echo 5. KV namespace: 选择 IPTV_CACHE
echo 6. 点击 Save
echo.
echo [3/3] 重新部署...
echo 绑定完成后，在 Dashboard 中点击 Deployments → Create new deployment
echo.

pause
