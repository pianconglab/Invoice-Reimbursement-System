#!/bin/sh
set -e

# 确保目录存在并有正确权限
mkdir -p /app/uploads /app/logs
chmod 755 /app/uploads /app/logs

# 初始化数据库
python -c "from app import init_db; init_db()"

# 启动应用，使用单个worker避免SQLite并发问题
exec gunicorn -w 1 -b 0.0.0.0:5000 --timeout 120 --keep-alive 5 app:app