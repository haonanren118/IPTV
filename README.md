# IPTV 源管理器

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.2-green.svg)](https://flask.palletsprojects.com)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://docker.com)
[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare-Pages-orange.svg)](https://pages.cloudflare.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于 Flask 的 IPTV 源自动管理工具，支持多种 IPTV 源格式（TXIPTV、HSMDTV、ZHGXTV、JSMPEG），自动测速筛选最优源，生成 M3U8 和 TXT 格式播放列表，通过 Cloudflare Pages + KV 全球分发。

## 🏗️ 架构说明

```
┌─────────────────┐      测速选优       ┌─────────────────┐
│  Docker (NAS)   │ ──────────────────→ │   Cloudflare KV  │
│  upload_and_    │    上传播放列表      │  m3u8_local      │
│  deploy.py      │                     │  txt_local       │
└─────────────────┘                     └────────┬────────┘
                                                  │ 读取
┌─────────────────┐      部署静态代码     ┌────────┴────────┐
│  GitHub Push    │ ──────────────────→ │ Cloudflare Pages │
│  deploy.yml     │                     │  index.html      │
└─────────────────┘                     │  functions/api   │
                                         └────────┬────────┘
                                                  │
                                         ┌────────┴────────┐
                                         │   用户访问       │
                                         │  /api/local/m3u8 │
                                         │  /api/local/txt  │
                                         └─────────────────┘
```

- **Docker（NAS）**：负责 IPTV 源抓取、测速筛选、生成播放列表，上传到 CF KV
- **GitHub Actions**：负责将静态代码（index.html、functions）部署到 CF Pages
- **Cloudflare Pages**：提供 API 接口，从 KV 读取数据返回给用户

## ✨ 功能特性

- 🔍 **自动源检测** - 从远程 API 获取 IPTV 源列表
- ⚡ **智能测速** - 多线程并行测速，筛选速度最快的前5个源
- 📺 **多格式支持** - 支持 TXIPTV、HSMDTV、ZHGXTV、JSMPEG 四种源格式
- 📄 **双格式输出** - 同时生成 M3U8 和 TXT 格式播放列表
- 🐳 **Docker 支持** - 提供 Dockerfile，一键部署到 NAS
- ☁️ **Cloudflare Pages** - 全球 CDN 加速，免费额度充足
- 🔄 **自动更新** - Docker 容器内每6小时自动检测并更新源列表
- 📊 **进度显示** - 实时显示测速进度条
- 🏷️ **频道标准化** - 自动统一 CCTV 和地方卫视频道名称
- 🖼️ **台标支持** - 自动生成频道台标 URL
- 🛡️ **降级机制** - 远程源失败时自动降级到本地 ZB.txt

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

Docker 容器负责 IPTV 源抓取、测速和上传，是整个系统的数据源。

1. **克隆仓库**
```bash
git clone https://github.com/haonanren118/IPTV.git
cd IPTV
```

2. **构建并运行**
```bash
docker build -t iptv-manager .
docker run -d -p 9998:9998 --name iptv-manager iptv-manager
```

3. **配置环境变量**（可选）
```bash
docker run -d -p 9998:9998 \
  -e CF_KV_TOKEN=你的token \
  -e UPLOAD_URL=https://your-project.pages.dev/api/upload \
  --name iptv-manager iptv-manager
```

4. **查看日志**
```bash
docker logs -f iptv-manager
```

### 方式二：Cloudflare Pages 部署

无需服务器，全球 CDN 加速，用于提供 API 接口和静态页面。

📖 **详细配置指南**：[GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)

**快速开始**：
1. Fork 本仓库到 GitHub
2. 配置 GitHub Secrets（只需一次）：
   - `CLOUDFLARE_API_TOKEN`：Cloudflare API 令牌
   - `CLOUDFLARE_ACCOUNT_ID`：Cloudflare 账号 ID
3. 在 Cloudflare Pages 中绑定 KV 命名空间（变量名：`IPTV_CACHE`）
4. 在 Cloudflare Pages 环境变量中设置 `API_KEY`（与 Docker 端 token 一致）
5. 推送代码到 master 分支，自动触发部署

部署后访问：`https://your-project.pages.dev`

播放源地址：
- M3U8: `https://your-project.pages.dev/api/local/m3u8`
- TXT: `https://your-project.pages.dev/api/local/txt`
- 合并: `https://your-project.pages.dev/api/all/m3u8`

### 方式三：直接运行

适用于本地开发和调试。

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **运行应用**
```bash
python app.py
```

3. **访问服务**
- 状态页面：http://localhost:5000/
- M3U8 播放列表：http://localhost:5000/iptv
- TXT 播放列表：http://localhost:5000/txt

### 方式四：NAS 部署

支持群晖 Synology、威联通 QNAP 等主流 NAS 系统。

📖 **详细部署指南**：[NAS_DEPLOYMENT.md](NAS_DEPLOYMENT.md)

**快速开始（群晖）**：
```bash
cd /volume1/docker
git clone https://github.com/haonanren118/IPTV.git
cd IPTV
docker-compose up -d
```

## 📁 项目结构

```
IPTV/
├── app.py                  # Flask 主应用（本地运行/调试用）
├── upload_and_deploy.py    # Docker 端：IPTV 源抓取 + 测速 + 上传到 CF KV
├── generate_playlist.py    # GitHub Actions 用：从 CF KV 同步播放列表（备用）
├── web_admin.py           # Web 管理界面
├── requirements.txt        # Python 依赖
├── Dockerfile             # Docker 构建文件
├── docker-compose.yml     # Docker Compose 配置
├── entrypoint.sh          # Docker 入口脚本
├── index.html             # 静态首页（CF Pages）
├── functions/             # CF Pages Functions
│   └── api/[[path]].js    # API 路由（读取 KV 数据）
├── .github/workflows/     # GitHub Actions
│   └── deploy.yml         # 自动部署工作流（部署静态代码到 CF Pages）
├── hsmd_address_list.txt  # HSMDTV 频道列表
├── ZB.txt                 # 本地降级频道列表
├── worker/                # Cloudflare Worker 版本
│   └── CF_DEPLOYMENT.md   # CF Worker 部署指南
├── README.md              # 项目说明文档
├── NAS_DEPLOYMENT.md      # NAS 部署指南
├── GITHUB_ACTIONS_SETUP.md # GitHub Actions 配置指南
├── CHANGELOG.md           # 更新日志
└── LICENSE                # MIT 许可证
```

## 🔌 API 接口

### Cloudflare Pages API（线上）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 服务状态查询 |
| `/api/local/m3u8` | GET | 获取 Docker 上传的 M3U8 播放列表 |
| `/api/local/txt` | GET | 获取 Docker 上传的 TXT 播放列表 |
| `/api/all/m3u8` | GET | 获取合并播放列表（公网 + 本地） |
| `/api/all/txt` | GET | 获取合并 TXT 播放列表 |
| `/api/upload` | POST | 上传播放列表到 KV（需 Token 认证） |

### Flask 本地 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务状态查询 |
| `/iptv` | GET | 获取 M3U8 格式播放列表 |
| `/txt` | GET | 获取 TXT 格式播放列表 |
| `/forceRetest` | GET | 强制重新测速并更新源 |

## ⚙️ 配置说明

### Docker 端配置（upload_and_deploy.py）

```python
# 上传配置
UPLOAD_URL = "https://your-project.pages.dev/api/upload"  # CF Pages 上传地址
UPLOAD_TOKEN = "你的API_KEY"                                # CF KV 认证 token

# 远程源配置
API_URL = "https://iptvs.pes.im"           # IPTV 源数据接口
TOP_N = 5                                  # 选择前 N 个最快源
MAX_WORKERS = 20                           # 最大并发线程数
HOST_SPEED_TEST_TIMEOUT = 15               # 单源测速超时时间（秒）
```

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CF_KV_TOKEN` | CF KV 上传认证 token | `cf-iptv-2025-x7m9k2p5q8r3t6v1` |
| `API_KEY` | 同上（备选变量名） | 同上 |
| `UPLOAD_URL` | CF Pages 上传地址 | `https://iptv-bfo.pages.dev/api/upload` |
| `ZB_FILE` | 本地降级频道文件路径 | `/app/ZB.txt` |

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
- **CDN/边缘计算**: Cloudflare Pages + Workers KV
- **容器化**: Docker

## 📝 更新日志

### v1.1.0 (2026-05-30)
- 🔄 架构重构：Docker 负责数据采集，CF Pages 负责分发
- 📤 Docker 端自动上传播放列表到 CF KV
- 🌐 GitHub Actions 简化为只部署静态代码
- 🛡️ 增加降级机制：远程源失败时使用本地 ZB.txt
- 🖥️ 新增 Web 管理界面
- 🔐 CF KV 上传 Token 认证

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
- [Cloudflare Pages](https://pages.cloudflare.com/) - 全球 CDN 边缘计算平台
- [GitHub](https://github.com/) - 代码托管平台
- [Gitee](https://gitee.com/) - 国内代码镜像

---

**⭐ 如果这个项目对你有帮助，欢迎点个 Star！**
