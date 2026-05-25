# 更新日志

所有项目的显著变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 计划中
- [ ] 添加 Web UI 管理界面
- [ ] 支持自定义频道分组
- [ ] 添加更多 EPG 数据源
- [ ] 支持播放列表导入/导出

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
