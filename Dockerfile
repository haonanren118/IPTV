FROM python:3.12-slim

WORKDIR /app

# 设置时区为北京时间
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install --no-cache-dir requests flask

# 复制脚本和播放列表源文件
COPY upload_and_deploy.py /app/upload_and_deploy.py
COPY web_admin.py /app/web_admin.py
COPY ZB.txt /app/ZB.txt

# 创建日志目录
RUN mkdir -p /app/logs

# 设置定时任务：每6小时运行一次
RUN echo "0 */6 * * * cd /app && python upload_and_deploy.py >> /app/logs/cron.log 2>&1" > /etc/cron.d/iptv-update && \
    chmod 0644 /etc/cron.d/iptv-update && \
    crontab /etc/cron.d/iptv-update

# 暴露 Web 管理端口
EXPOSE 9998

# 启动 Web 管理界面和定时任务
CMD ["sh", "-c", "python /app/upload_and_deploy.py && python /app/web_admin.py & cron -f"]
