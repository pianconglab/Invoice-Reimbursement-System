FROM python:3.13.5-bookworm

# 设置工作目录
WORKDIR /app

# 为了利用 Docker 的缓存机制，先复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖，并清除缓存
# RUN pip install --no-cache-dir -r requirements.txt
# 使用腾讯云镜像源
RUN pip install -i https://mirrors.cloud.tencent.com/pypi/simple --no-cache-dir -r requirements.txt

# 复制项目中的所有其他文件（.dockerignore中指定的文件和目录会被忽略）
COPY . .

# 暴露应用程序运行的端口
EXPOSE 5000

# Gunicorn 进程数
ENV GUNICORN_WORKERS=2

# 添加健康检查，用于监控容器状态
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:5000 || exit 1

# 启动系统
ENTRYPOINT ["/app/entrypoint.sh"]
