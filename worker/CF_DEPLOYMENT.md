# Cloudflare Workers 部署指南

将 IPTV 源管理器部署到 Cloudflare Workers，获得全球 CDN 加速的播放源接口。

## ✨ 优势

- 🌍 **全球加速** - Cloudflare 边缘节点，访问速度快
- 🆓 **免费额度** - Workers 免费版每天 10 万次请求
- ⚡ **无需服务器** - Serverless 架构，免运维
- 🔄 **自动更新** - Cron Trigger 定时更新播放列表
- 💾 **KV 缓存** - 数据持久化存储

## 📋 前置要求

- [Node.js](https://nodejs.org/) 18+
- [Cloudflare 账号](https://dash.cloudflare.com/sign-up)
- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/)

## 🚀 部署步骤

### 1. 安装 Wrangler CLI

```bash
npm install -g wrangler
```

### 2. 登录 Cloudflare

```bash
wrangler login
```

浏览器会自动打开授权页面，点击 "Allow" 完成授权。

### 3. 创建 KV 命名空间

```bash
cd worker
wrangler kv:namespace create "IPTV_CACHE"
```

执行后会输出类似：

```
{ binding = "IPTV_CACHE", id = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" }
```

**将输出的 `id` 填入 `wrangler.toml`**：

```toml
[[kv_namespaces]]
binding = "IPTV_CACHE"
id = "你的KV命名空间ID"
```

### 4. 本地测试

```bash
npm install
npm run dev
```

访问 http://localhost:8787 查看效果。

### 5. 部署到 Cloudflare

```bash
npm run deploy
```

部署成功后会输出 Worker 的访问地址：

```
https://iptv-manager.你的子域名.workers.dev
```

### 6. 绑定自定义域名（可选）

1. 进入 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 选择你的域名 → Workers Routes
3. 添加路由：`iptv.yourdomain.com/*` → `iptv-manager`

## 🔌 接口地址

部署完成后，你将获得以下接口：

| 接口 | 说明 | 示例 |
|------|------|------|
| `/` | 服务状态 | `https://iptv.yourdomain.com/` |
| `/iptv` | M3U8 播放列表 | `https://iptv.yourdomain.com/iptv` |
| `/txt` | TXT 播放列表 | `https://iptv.yourdomain.com/txt` |
| `/forceRetest` | 强制更新 | `https://iptv.yourdomain.com/forceRetest` |

## 📺 在播放器中使用

将以下地址添加到 IPTV 播放器中：

**M3U8 格式**（推荐）：
```
https://iptv.yourdomain.com/iptv
```

**TXT 格式**：
```
https://iptv.yourdomain.com/txt
```

支持以下播放器：
- TiviMate
- IPTV Pro
- VLC
- PotPlayer
- KODI

## ⚙️ 配置说明

在 `src/worker.js` 顶部可修改配置：

```javascript
const TOP_N = 5;                  // 选择前 N 个最快源
const SPEED_TEST_TIMEOUT = 8000;  // 测速超时（毫秒）
const MIN_SPEED_MBPS = 1.5;       // 最低速度阈值（MB/s）
const CACHE_TTL = 3600;           // 缓存有效期（秒）
```

在 `wrangler.toml` 中可修改定时任务频率：

```toml
[triggers]
crons = ["0 */6 * * *"]  # 每6小时更新一次
```

## 🔄 更新与维护

### 更新代码

```bash
git pull
npm run deploy
```

### 查看日志

```bash
npm run tail
```

### 手动触发更新

```bash
curl https://iptv.yourdomain.com/forceRetest
```

## ⚠️ 注意事项

1. **CF Worker 免费版限制**：
   - CPU 时间：每请求最多 10ms（付费版 30ms）
   - 每天请求：10 万次
   - KV 读取：每天 10 万次
   - KV 写入：每天 1000 次

2. **测速限制**：CF Worker 出口带宽有限，测速结果可能不如本地部署准确

3. **Cron Trigger**：免费版 Cron 最小间隔为 15 分钟，建议设置为 6 小时

## 🛠️ 故障排除

### 部署失败

```bash
# 检查 wrangler 版本
wrangler --version

# 更新 wrangler
npm update wrangler
```

### KV 读写失败

确认 `wrangler.toml` 中的 KV namespace ID 正确：

```bash
wrangler kv:namespace list
```

### 播放列表为空

1. 检查日志：`npm run tail`
2. 手动触发更新：`curl https://your-worker.dev/forceRetest`
3. 检查 API 是否可访问：`curl https://iptvs.pes.im`

---

## 💬 技术支持

- **项目地址**：[GitHub](https://github.com/haonanren118/IPTV) | [Gitee](https://gitee.com/yygitee118/IPTV)
- **问题反馈**：[GitHub Issues](https://github.com/haonanren118/IPTV/issues) | [Gitee Issues](https://gitee.com/yygitee118/IPTV/issues)
- **交流 QQ 群**：**708144970**

---

**最后更新**：2025-05-24
