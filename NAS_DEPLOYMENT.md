# NAS 部署指南

本文档详细介绍如何在主流 NAS 设备上部署 IPTV 源管理器。

## 📋 目录

- [群晖 Synology 部署](#群晖-synology-部署)
- [威联通 QNAP 部署](#威联通-qnap-部署)
- [其他 NAS 系统](#其他-nas-系统)
- [常见问题](#常见问题)

---

## 群晖 Synology 部署

### 方式一：通过 Docker 套件（推荐）

#### 前置要求
- DSM 6.0 或更高版本
- 已安装 Docker 套件（从套件中心安装）

#### 步骤 1：下载项目文件

**方法 A：通过 Git（推荐）**

1. 在群晖上安装 Git Server 套件（可选）
2. 通过 SSH 连接到群晖：
```bash
ssh admin@你的群晖IP
```
3. 进入 Docker 目录并克隆项目：
```bash
cd /volume1/docker
# GitHub
git clone https://github.com/haonanren118/IPTV.git
# 或 Gitee（国内推荐）
git clone https://gitee.com/yygitee118/IPTV.git
cd IPTV
```

**方法 B：手动上传**

1. 下载项目 ZIP：
   - GitHub：https://github.com/haonanren118/IPTV/archive/refs/heads/master.zip
   - Gitee：https://gitee.com/yygitee118/IPTV/repository/archive/master.zip
2. 解压到电脑本地
3. 通过群晖 File Station 上传到 `/volume1/docker/IPTV/`

#### 步骤 2：构建 Docker 镜像

1. 打开 **Docker** 套件
2. 切换到 **映像** 选项卡
3. 点击 **新增** → **从文件添加**（如果已有镜像）
   
   或通过 SSH 构建：
```bash
cd /volume1/docker/IPTV
docker build -t iptv-manager:latest .
```

#### 步骤 3：配置并运行容器

**方法 A：通过 Docker UI**

1. 双击镜像启动容器
2. **高级设置**：
   - **网络**：选择 `bridge` 模式
   - **端口设置**：
     - 本地端口：`5000`（或自定义）
     - 容器端口：`5000`
   - **卷**（可选，用于数据持久化）：
     - 文件/文件夹：`/volume1/docker/IPTV/data`
     - 装载路径：`/app/data`
   - **环境变量**（可选）：
     - `TZ=Asia/Shanghai`

3. 点击 **应用** 完成创建

**方法 B：通过 docker-compose（推荐）**

1. 在项目目录创建 `docker-compose.yml`：
```yaml
version: '3'
services:
  iptv-manager:
    build: .
    container_name: iptv-manager
    restart: always
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
```

2. 通过 SSH 运行：
```bash
cd /volume1/docker/IPTV
docker-compose up -d
```

#### 步骤 4：验证部署

打开浏览器访问：`http://你的群晖IP:5000/`

---

## 威联通 QNAP 部署

### 通过 Container Station

#### 前置要求
- QTS 4.2 或更高版本
- 已安装 Container Station

#### 步骤 1：准备项目文件

1. 通过 File Station 创建共享文件夹，如 `Docker/IPTV`
2. 下载项目文件并上传到该目录

#### 步骤 2：构建镜像

**方法 A：通过 Container Station UI**

1. 打开 **Container Station**
2. 点击 **创建** → **构建映像**
3. 选择项目目录中的 `Dockerfile`
4. 设置镜像名称：`iptv-manager`
5. 点击 **构建**

**方法 B：通过 SSH**

```bash
ssh admin@你的NAS_IP
cd /share/Docker/IPTV
docker build -t iptv-manager:latest .
```

#### 步骤 3：运行容器

**使用 docker-compose（推荐）**

1. 创建 `docker-compose.yml`：
```yaml
version: '3'
services:
  iptv-manager:
    image: iptv-manager:latest
    container_name: iptv-manager
    restart: always
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
```

2. 运行容器：
```bash
docker-compose up -d
```

**或使用 Container Station UI**

1. 在 Container Station 中点击 **创建容器**
2. 选择 `iptv-manager` 镜像
3. 配置：
   - 名称：`iptv-manager`
   - 网络：`bridge`
   - 端口转发：主机 `5000` → 容器 `5000`
4. 点击 **创建**

#### 步骤 4：访问服务

浏览器访问：`http://你的NAS_IP:5000/`

---

## 其他 NAS 系统

### 华芸 Asustor

1. 安装 **Docker** 应用（从 App Central）
2. 按照通用 Docker 部署步骤操作

### 铁威马 TerraMaster

1. 安装 **Docker** 应用
2. 通过 SSH 或 Docker UI 部署

### 自建 NAS（OpenMediaVault / TrueNAS）

**OpenMediaVault:**
1. 安装 OMV-Extras 插件
2. 启用 Docker 服务
3. 使用 Portainer 或命令行部署

**TrueNAS Scale:**
1. 使用内置的 Apps 功能
2. 或通过 SSH 使用 Docker 命令

---

## 通用 Docker 命令

### 构建镜像
```bash
docker build -t iptv-manager:latest .
```

### 运行容器
```bash
docker run -d \
  --name iptv-manager \
  --restart always \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e TZ=Asia/Shanghai \
  iptv-manager:latest
```

### 查看日志
```bash
docker logs -f iptv-manager
```

### 停止容器
```bash
docker stop iptv-manager
```

### 重启容器
```bash
docker restart iptv-manager
```

### 更新部署
```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 反向代理配置（可选）

### 群晖反向代理

1. 打开 **控制面板** → **登录门户** → **高级** → **反向代理服务器**
2. 点击 **新增**：
   - 描述：`IPTV Manager`
   - 来源：
     - 协议：`HTTPS`
     - 主机名：`iptv.你的域名.com`
     - 端口：`443`
   - 目的地：
     - 协议：`HTTP`
     - 主机名：`localhost`
     - 端口：`5000`
3. 保存并应用

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name iptv.yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 常见问题

### Q1: 端口被占用怎么办？

**群晖**：检查是否有其他服务占用 5000 端口，修改为其他端口如 `5001`

```bash
# 查看端口占用
netstat -tulpn | grep 5000
```

### Q2: 如何实现开机自启？

Docker 容器设置 `restart: always` 或 `restart: unless-stopped` 即可自动启动。

### Q3: 如何备份数据？

备份以下文件/目录：
- `iptv_sources.m3u8`
- `iptv_sources.txt`
- `hsmd_address_list.txt`

### Q4: 如何查看运行状态？

```bash
# 查看容器状态
docker ps | grep iptv-manager

# 查看实时日志
docker logs -f iptv-manager

# 进入容器
docker exec -it iptv-manager /bin/bash
```

### Q5: 测速速度很慢？

- 检查 NAS 网络连接
- 调整 `MAX_WORKERS` 参数（在 `app.py` 中）
- 确保足够的系统资源

### Q6: 如何更新到最新版本？

```bash
cd /volume1/docker/IPTV
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 性能优化建议

1. **资源限制**：在 docker-compose 中添加资源限制
```yaml
services:
  iptv-manager:
    # ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
```

2. **定时任务调整**：根据需求调整更新频率
```python
# 每12小时更新一次（减少资源消耗）
scheduler.add_job(func=scheduled_task, trigger="interval", hours=12)
```

3. **使用 SSD 缓存**：如果 NAS 支持，为 Docker 目录启用 SSD 缓存

---

## 技术支持

- **项目地址**：[GitHub](https://github.com/haonanren118/IPTV) | [Gitee](https://gitee.com/yygitee118/IPTV)
- **问题反馈**：[GitHub Issues](https://github.com/haonanren118/IPTV/issues) | [Gitee Issues](https://gitee.com/yygitee118/IPTV/issues)
- **交流 QQ 群**：**708144970**

---

**最后更新**：2025-05-24
