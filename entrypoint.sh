#!/bin/sh
set -e

# 确保目录存在并有正确权限
mkdir -p /app/uploads /app/logs
chmod 755 /app/uploads /app/logs

# 初始化数据库
python -c "from app import init_db; init_db()"

# 启动应用，使用单个 gevent worker，并增加 worker-connections 数量
# -k gevent: 指定使用 gevent 异步 worker
# --worker-connections: 指定每个 worker 能处理的最大并发连接数
exec gunicorn -w 1 -k gevent --worker-connections 1000 -b 0.0.0.0:5000 --timeout 120 --keep-alive 5 app:app