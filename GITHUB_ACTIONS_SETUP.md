# GitHub Actions 自动部署配置

本指南说明如何配置 GitHub Actions 实现自动部署到 Cloudflare Pages。

## 🏗️ 当前架构

```
Docker (NAS) → 测速选优 → 上传到 CF KV
                              ↓
GitHub Push → 部署静态代码 → CF Pages
                              ↓
用户访问 → CF Pages API → 读取 KV 数据
```

GitHub Actions 现在只负责**部署静态代码**（index.html、functions 等）到 Cloudflare Pages，不再执行 IPTV 源测速。播放列表数据由 Docker 容器负责采集和上传。

## 🚀 功能特性

- ✅ 推送到 master/main 分支时自动部署
- ✅ 支持手动触发部署
- ✅ 部署速度快（约 30 秒）

## 📋 前置要求

1. GitHub 仓库已 Fork
2. Cloudflare 账号和 Pages 项目已创建
3. 拥有 Cloudflare API Token

## 🔑 配置 Secrets

### 步骤 1：获取 Cloudflare API Token

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 点击右上角头像 → **My Profile**
3. 选择 **API Tokens** 标签
4. 点击 **Create Token**
5. 选择 **Custom token** 模板
6. 填写配置：
   - **Token name**: `GitHub Actions Deploy`
   - **Permissions**:
     - `Cloudflare Pages:Edit`
     - `Account:Read`
   - **Account Resources**: Include - 你的账号
7. 点击 **Continue to summary** → **Create Token**
8. **复制 Token**（只显示一次！）

### 步骤 2：获取 Account ID

1. 在 Cloudflare Dashboard 右侧边栏
2. 找到 **Account ID**（一串字母数字）
3. 复制备用

### 步骤 3：在 GitHub 设置 Secrets

1. 打开你的 GitHub 仓库
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 添加以下 Secrets：

| Secret 名称 | 值 | 说明 |
|------------|-----|------|
| `CLOUDFLARE_API_TOKEN` | 步骤1复制的 Token | API 访问令牌 |
| `CLOUDFLARE_ACCOUNT_ID` | 步骤2复制的 ID | Cloudflare 账号 ID |

### 步骤 4：配置 Cloudflare Pages 环境变量

在 Cloudflare Dashboard → Pages → 你的项目 → Settings → Environment variables 中添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `API_KEY` | 与 Docker 端 `CF_KV_TOKEN` 一致的值 | KV 上传认证 token |

### 步骤 5：绑定 KV 命名空间

在 Cloudflare Dashboard → Pages → 你的项目 → Settings → Functions → KV namespace bindings 中：

- **Variable name**: `IPTV_CACHE`
- **KV namespace**: 创建新的或选择已有的

## 🚀 触发部署

### 方式 1：自动部署（推荐）

推送代码到 master/main 分支：

```bash
git add .
git commit -m "更新代码"
git push origin master
```

GitHub Actions 会自动运行并部署。

### 方式 2：手动触发

1. 打开 GitHub 仓库
2. 点击 **Actions** 标签
3. 选择 **部署到 Cloudflare Pages** 工作流
4. 点击 **Run workflow** → **Run workflow**

## 📊 查看部署状态

1. 打开 GitHub 仓库
2. 点击 **Actions** 标签
3. 查看最近的部署记录
4. 点击部署记录查看详细日志

## 🔧 故障排除

### 部署失败：权限错误

**错误信息**：`Authentication error`

**解决方案**：
1. 检查 `CLOUDFLARE_API_TOKEN` 是否正确
2. 检查 Token 权限是否包含 `Cloudflare Pages:Edit`
3. 重新创建 Token 并更新 Secret

### 部署失败：项目不存在

**错误信息**：`Project not found`

**解决方案**：
1. 确保 Cloudflare Pages 项目已创建
2. 检查 `deploy.yml` 中的 `projectName` 是否与 Pages 项目名称一致
3. 修改 `projectName` 后重新推送

### 播放列表为空或未更新

**解决方案**：
1. 检查 Docker 容器是否正常运行：`docker logs -f iptv-manager`
2. 确认 Docker 端上传是否成功（日志中应显示 `✅ 上传成功`）
3. 检查 CF Pages 环境变量 `API_KEY` 是否与 Docker 端 `CF_KV_TOKEN` 一致
4. 访问 `/api/status` 查看 `local_last_update` 时间

## 📝 工作流说明

当前 `.github/workflows/deploy.yml` 的功能：

```yaml
# 触发条件：push 到 master/main 或手动触发
on:
  push:
    branches: [master, main]
  workflow_dispatch:

# 步骤：
# 1. Checkout 代码
# 2. 部署到 Cloudflare Pages（使用 cloudflare/pages-action@v1）
# 3. 验证部署
```

> **注意**：旧版本的 `deploy.yml` 包含 Python 环境安装和播放列表生成步骤，
> 这些已在 v1.1.0 中移除。播放列表数据现在由 Docker 容器负责生成和上传。

## 💡 最佳实践

1. **保护分支**：在 GitHub Settings → Branches 中保护 master 分支
2. **代码审查**：开启 Pull Request 审查，确保代码质量
3. **部署预览**：PR 会自动创建预览部署，确认无误后再合并
4. **监控日志**：定期查看 Actions 日志和 Docker 容器日志

## 📞 支持

遇到问题？
- 查看 [Actions 日志](https://github.com/haonanren118/IPTV/actions)
- 加入 QQ 群：**708144970**
- 提交 [GitHub Issue](https://github.com/haonanren118/IPTV/issues)
