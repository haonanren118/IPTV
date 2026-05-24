FROM python:3.12-slim

WORKDIR /app

# 设置时区为北京时间
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（app.py + web_admin + upload 共用）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制所有脚本和播放列表源文件
COPY app.py /app/app.py
COPY upload_and_deploy.py /app/upload_and_deploy.py
COPY web_admin.py /app/web_admin.py
COPY ZB.txt /app/ZB.txt
COPY entrypoint.sh /app/entrypoint.sh

# 创建日志目录
RUN mkdir -p /app/logs && chmod +x /app/entrypoint.sh

# 暴露端口：5000(公网源扫描) + 9998(Web管理界面)
EXPOSE 5000 9998

# 统一入口：同时启动 app.py + upload_and_deploy.py + web_admin.py
CMD ["/app/entrypoint.sh"]
