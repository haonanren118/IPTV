# 更新日志

所有项目的显著变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 计划中
- [ ] 支持自定义频道分组
- [ ] 添加更多 EPG 数据源
- [ ] 支持播放列表导入/导出
- [ ] 多源负载均衡（自动切换故障源）

## [1.1.0] - 2026-05-30

### 🔄 架构重构
- Docker 端负责 IPTV 源抓取、测速筛选、上传播放列表到 CF KV
- GitHub Actions 简化为只部署静态代码到 CF Pages（不再测速）
- CF Pages 提供 API 接口，从 KV 读取数据返回给用户
- 新增架构说明文档和流程图

### ✨ 新增
- `upload_and_deploy.py`：Docker 端自动上传播放列表到 CF KV
- CF KV 上传 Token 认证机制
- 降级机制：远程源失败时自动使用本地 ZB.txt
- Web 管理界面 (`web_admin.py`)
- 首页优先显示 Docker 本地源更新时间 (`local_last_update`)
- 环境变量配置支持（`CF_KV_TOKEN`、`API_KEY`、`UPLOAD_URL`）

### 🔧 变更
- `generate_playlist.py`：移除测速逻辑，改为从 CF KV 读取 Docker 上传的播放列表
- `deploy.yml`：移除 Python 安装和播放列表生成步骤，只保留静态代码部署
- `index.html`：优先显示 `local_last_update` 而非 `last_update`
- API 接口路径调整：`/api/local/m3u8`、`/api/local/txt` 作为主要播放源

### 🔒 安全
- CF KV 上传接口增加 Token 认证
- 默认 token 更新为 `cf-iptv-2025-x7m9k2p5q8r3t6v1`

## [1.0.4] - 2025-05-24

### ✨ 新增
- 初始版本发布
- 支持 TXIPTV、HSMDTV、ZHGXTV、JSMPEG 四种 IPTV 源格式
- 多线程并行测速，自动筛选最优源
- 生成 M3U8 和 TXT 双格式播放列表
- 自动更新机制（每6小时）
- Docker 容器化支持
- 实时测速进度显示
- 频道名称标准化（CCTV、卫视等）
- 自动生成频道台标 URL
- 强制重新测速接口

### 🔧 技术特性
- Flask 3.1.2 Web 框架
- APScheduler 任务调度
- 多线程并发处理
- 自动版本检查与更新
- 进程锁防止重复运行

## [1.0.0] - 2025-05-20

### 🎉 项目启动
- 项目初始化
- 基础架构搭建

---

**贡献者**: [@haonanren118](https://github.com/haonanren118)
