# GitHub Actions 自动部署配置

本指南说明如何配置 GitHub Actions 实现自动部署到 Cloudflare Pages。

## 🚀 功能特性

- ✅ 自动检测并创建 KV 命名空间
- ✅ 自动更新 `wrangler.toml` 配置
- ✅ 推送到 master/main 分支时自动部署
- ✅ 支持手动触发部署
- ✅ 首次部署后自动绑定 KV

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
     - `Zone:Read` (可选)
     - `Workers KV Storage:Edit`
   - **Account Resources**: Include - 你的账号
   - **Zone Resources**: Include - All zones (或指定域名)
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
3. 选择 **Deploy to Cloudflare Pages** 工作流
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

### KV 绑定失败

**错误信息**：`KV namespace not found`

**解决方案**：
1. 工作流会自动创建 KV 命名空间
2. 检查工作流日志中的 KV 创建步骤
3. 手动在 Dashboard 创建 KV 并更新 `wrangler.toml`

### 首次部署后播放列表为空

**解决方案**：
1. 访问 `https://your-project.pages.dev/api/forceRetest`
2. 等待 10-30 秒
3. 刷新页面查看状态

## 📝 更新工作流

如需修改部署配置，编辑 `.github/workflows/deploy.yml` 文件。

常见修改：

### 修改触发分支

```yaml
on:
  push:
    branches: [ master, main, develop ]  # 添加 develop 分支
```

### 添加定时自动部署

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # 每6小时自动部署
```

### 修改项目名

```yaml
- name: Deploy to Cloudflare Pages
  uses: cloudflare/pages-action@v1
  with:
    projectName: your-project-name  # 修改这里
```

## 💡 最佳实践

1. **保护分支**：在 GitHub Settings → Branches 中保护 master 分支
2. **代码审查**：开启 Pull Request 审查，确保代码质量
3. **部署预览**：PR 会自动创建预览部署，确认无误后再合并
4. **监控日志**：定期查看 Actions 日志，及时发现异常

## 📞 支持

遇到问题？
- 查看 [Actions 日志](https://github.com/你的用户名/IPTV/actions)
- 加入 QQ 群：**708144970**
- 提交 [GitHub Issue](https://github.com/haonanren118/IPTV/issues)
