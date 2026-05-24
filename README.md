# IPTV 源管理器

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.2-green.svg)](https://flask.palletsprojects.com)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于 Flask 的 IPTV 源自动管理工具，支持多种 IPTV 源格式（TXIPTV、HSMDTV、ZHGXTV、JSMPEG），自动测速筛选最优源，生成 M3U8 和 TXT 格式播放列表。

## ✨ 功能特性

- 🔍 **自动源检测** - 从远程 API 获取 IPTV 源列表
- ⚡ **智能测速** - 多线程并行测速，筛选速度最快的前5个源
- 📺 **多格式支持** - 支持 TXIPTV、HSMDTV、ZHGXTV、JSMPEG 四种源格式
- 📄 **双格式输出** - 同时生成 M3U8 和 TXT 格式播放列表
- 🐳 **Docker 支持** - 提供 Dockerfile，一键部署
- 🔄 **自动更新** - 每6小时自动检测并更新源列表
- 📊 **进度显示** - 实时显示测速进度条
- 🏷️ **频道标准化** - 自动统一 CCTV 和地方卫视频道名称
- 🖼️ **台标支持** - 自动生成频道台标 URL

## 🚀 快速开始

### 方式一：直接运行

1. **克隆仓库**
```bash
# GitHub
git clone https://github.com/haonanren118/IPTV.git
# 或 Gitee
git clone https://gitee.com/yygitee118/IPTV.git
cd IPTV
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **运行应用**
```bash
python app.py
```

4. **访问服务**
- 状态页面：http://localhost:5000/
- M3U8 播放列表：http://localhost:5000/iptv
- TXT 播放列表：http://localhost:5000/txt

### 方式二：Docker 部署

1. **构建镜像**
```bash
docker build -t iptv-manager .
```

2. **运行容器**
```bash
docker run -d -p 5000:5000 --name iptv-manager iptv-manager
```

3. **查看日志**
```bash
docker logs -f iptv-manager
```

### 方式三：Cloudflare Pages 部署（推荐）

无需服务器，全球 CDN 加速，免费额度充足，支持 Git 自动部署。

#### 方案 A：GitHub Actions 自动部署（推荐）

配置一次，永久自动部署。

📖 **详细配置指南**：[GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)

**快速开始**：
1. Fork 本仓库到 GitHub
2. 配置 GitHub Secrets（只需一次）：
   - `CLOUDFLARE_API_TOKEN`：Cloudflare API 令牌
   - `CLOUDFLARE_ACCOUNT_ID`：Cloudflare 账号 ID
3. 推送代码到 master 分支，自动触发部署

#### 方案 B：手动部署

1. Fork 本仓库到 GitHub
2. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
3. 选择 **Pages** → **Create a project** → **Connect to Git**
4. 选择你的仓库，点击 **Begin setup**
5. **Build settings**：
   - Build command:（留空）
   - Build output directory:（留空）
6. 点击 **Save and Deploy**
7. 在 **Settings** → **Functions** → **KV namespace bindings** 中绑定 KV：
   - Variable name: `IPTV_CACHE`
   - KV namespace: 创建新的或选择已有的

部署后访问：`https://your-project.pages.dev`

播放源地址：
- M3U8: `https://your-project.pages.dev/api/iptv`
- TXT: `https://your-project.pages.dev/api/txt`

### 方式四：Cloudflare Workers 部署

纯 Workers 部署，适合需要更灵活配置的场景。

📖 **详细部署指南**：[worker/CF_DEPLOYMENT.md](worker/CF_DEPLOYMENT.md)

**快速开始**：
```bash
cd worker
npm install
wrangler login
wrangler kv:namespace create "IPTV_CACHE"
npm run deploy
```

部署后获得播放源地址：`https://your-worker.dev/iptv`

### 方式五：NAS 部署

支持群晖 Synology、威联通 QNAP 等主流 NAS 系统。

📖 **详细部署指南**：[NAS_DEPLOYMENT.md](NAS_DEPLOYMENT.md)

**快速开始（群晖）**：
```bash
# SSH 连接到群晖
cd /volume1/docker
git clone https://github.com/haonanren118/IPTV.git
cd IPTV
docker-compose up -d
```

## 📁 项目结构

```
IPTV/
├── app.py                  # 主应用程序（Python 版）
├── requirements.txt        # Python 依赖
├── Dockerfile             # Docker 构建文件
├── docker-compose.yml     # Docker Compose 配置
├── .dockerignore          # Docker 忽略文件
├── .gitignore             # Git 忽略文件
├── index.html             # 静态首页（CF Pages 用）
├── wrangler.toml          # CF Pages 配置
├── functions/             # CF Pages Functions
│   └── api/[[path]].js    # API 路由
├── .github/workflows/     # GitHub Actions
│   └── deploy.yml         # 自动部署工作流
├── hsmd_address_list.txt  # HSMDTV 频道列表
├── iptv_sources.m3u8      # 生成的 M3U8 播放列表
├── iptv_sources.txt       # 生成的 TXT 播放列表
├── worker/                # Cloudflare Worker 版本
│   ├── src/worker.js      # Worker 核心逻辑
│   ├── wrangler.toml      # Worker 配置
│   ├── package.json       # Node.js 依赖
│   └── CF_DEPLOYMENT.md   # CF 部署指南
├── README.md              # 项目说明文档
├── NAS_DEPLOYMENT.md      # NAS 部署指南
├── GITHUB_ACTIONS_SETUP.md # GitHub Actions 配置指南
├── CHANGELOG.md           # 更新日志
└── LICENSE                # MIT 许可证
```

## 🔌 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务状态查询 |
| `/iptv` | GET | 获取 M3U8 格式播放列表 |
| `/txt` | GET | 获取 TXT 格式播放列表 |
| `/forceRetest` | GET | 强制重新测速并更新源 |

### 接口示例

**获取服务状态**
```bash
curl http://localhost:5000/
```
响应：
```json
{
  "status": "running",
  "last_run": "2025-05-24 10:30:00",
  "message": "Visit /iptv for m3u8 playlist, /txt for text playlist."
}
```

**强制重新测速**
```bash
curl http://localhost:5000/forceRetest
```

## ⚙️ 配置说明

主要配置项在 `app.py` 文件中的常量定义：

```python
# API 配置
API_URL = "https://iptvs.pes.im"           # IPTV 源数据接口
EPG_URL = "https://epg.zsdc.eu.org/t.xml"  # 电子节目单地址

# 测速配置
MAX_WORKERS = 20                           # 最大并发线程数
TOP_N = 5                                  # 选择前 N 个最快源
HOST_SPEED_TEST_TIMEOUT = 15               # 单源测速超时时间（秒）
SPEED_TEST_BATCH_SIZE = 60                 # 每批测速数量

# 更新频率
scheduler.add_job(func=scheduled_task, trigger="interval", hours=6)  # 每6小时更新
```

## 📺 支持的源格式

### 1. TXIPTV
- 接口：`http://{host}/iptv/live/1000.json?key=txiptv`
- 特点：JSON 格式，频道信息完整

### 2. HSMDTV
- 接口：`http://{host}/newlive/live/hls/{id}/live.m3u8`
- 特点：基于 `hsmd_address_list.txt` 中的频道列表

### 3. ZHGXTV
- 接口：`http://{host}/ZHGXTV/Public/json/live_interface.txt`
- 特点：文本格式，逗号分隔

### 4. JSMPEG
- 接口：`http://{host}/streamer/list`
- 特点：流媒体服务器列表

## 🛠️ 技术栈

- **后端框架**: Flask 3.1.2
- **任务调度**: APScheduler 3.11.2
- **HTTP 请求**: Requests 2.32.5
- **WSGI 服务器**: Eventlet 0.40.4
- **容器化**: Docker

## 📝 更新日志

### v1.0.4 (2025-05-24)
- ✨ 初始版本发布
- 🔧 支持四种 IPTV 源格式
- ⚡ 多线程并行测速
- 🐳 Docker 支持

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 💬 技术支持

- **项目地址**：[GitHub](https://github.com/haonanren118/IPTV) | [Gitee](https://gitee.com/yygitee118/IPTV)
- **问题反馈**：[GitHub Issues](https://github.com/haonanren118/IPTV/issues) | [Gitee Issues](https://gitee.com/yygitee118/IPTV/issues)
- **交流 QQ 群**：**708144970**

## 🙏 致谢

- [Flask](https://flask.palletsprojects.com/) - 轻量级 Web 框架
- [APScheduler](https://apscheduler.readthedocs.io/) - Python 任务调度库
- [GitHub](https://github.com/) - 代码托管平台
- [Gitee](https://gitee.com/) - 国内代码镜像

---

**⭐ 如果这个项目对你有帮助，欢迎点个 Star！**
