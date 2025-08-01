# 骈聪课题组发票报销系统

一个简洁的骈聪课题组发票报销管理系统，支持匿名用户提交申请和管理员审批功能。

## 功能特点

- **匿名申请**：科研人员无需注册即可提交报销申请
- **文件上传**：支持多文件上传，自动重命名为发票号码格式
- **审批管理**：管理员可查看、审批和导出所有申请
- **数据导出**：支持导出Excel格式的申请数据
- **状态跟踪**：申请状态实时更新（待审批/报销中/已报销/驳回）
- **完整日志**：详细记录所有操作、参数和结果，支持在线查看

## 安装运行

### 直接安装

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 运行系统：

```bash
python app.py
```

### 使用 Docker Compose 安装（推荐）

#### 方式一：使用部署脚本（最简单）

```bash
# 启动服务
./deploy.sh start

# 查看状态
./deploy.sh status

# 查看日志
./deploy.sh logs

# 停止服务
./deploy.sh stop

# 备份数据
./deploy.sh backup
```

#### 方式二：直接使用 Docker Compose

1. 启动服务：

```bash
# 使用简化版配置（SQLite数据库）
docker compose -f docker-compose.simple.yml up -d --build

# 或使用完整版配置（包含PostgreSQL和Redis）
docker compose up -d --build
```

2. 停止服务：

```bash
# 停止简化版
docker compose -f docker-compose.simple.yml down

# 停止完整版
docker compose down
```

3. 查看服务状态：

```bash
# 查看简化版状态
docker compose -f docker-compose.simple.yml ps

# 查看日志
docker compose -f docker-compose.simple.yml logs -f web
```

### 使用 Docker 单容器安装（传统方式）

1. 构建镜像：

```bash
#!/bin/bash
sudo docker build -t invoice-app:latest .
sudo docker rm -f invoice-app
sudo docker run -d \
  --name invoice-app \
  -p 5000:5000 \
  -v "$(pwd)/uploads:/app/uploads" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/reimbursement.db:/app/reimbursement.db" \
  --restart unless-stopped \
  invoice-app:latest
```

## 访问系统

- 用户端：<http://localhost:5000>
- 管理后台：<http://localhost:5000/admin/login>

默认管理员账户

- 用户名：`admin`
- 密码：`admin123`

## Docker Compose 配置说明

### 简化版配置 (docker-compose.simple.yml)

- **Web服务**：Flask应用 + Gunicorn
- **数据库**：SQLite（文件挂载）
- **存储**：本地目录挂载（uploads、logs）
- **网络**：独立的bridge网络

### 完整版配置 (docker-compose.yml)

- **Web服务**：Flask应用 + Gunicorn
- **数据库**：PostgreSQL 15
- **缓存**：Redis 7
- **存储**：数据卷持久化
- **网络**：服务间内部通信
- **健康检查**：所有服务都配置了健康检查

### 环境变量配置

可以通过 `.env` 文件自定义配置：

```bash
# 应用配置
FLASK_ENV=production
GUNICORN_WORKERS=2

# 端口配置
WEB_PORT=5000

# 容器名称
WEB_CONTAINER_NAME=invoice-web
```

## 目录结构

```text
fapiao/
├── app.py                      # 主应用文件
├── requirements.txt            # Python依赖
├── Dockerfile                  # Docker镜像构建文件
├── entrypoint.sh              # 容器启动脚本
├── docker-compose.yml         # 完整版Docker Compose配置
├── docker-compose.simple.yml  # 简化版Docker Compose配置
├── .env                       # 环境变量配置
├── templates/                 # HTML模板
│   ├── base.html
│   ├── index.html
│   ├── success.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   └── admin_detail.html
├── uploads/                   # 文件上传目录
├── logs/                      # 日志文件目录（自动生成）
│   └── app.log               # 应用日志
├── backup/                    # 数据备份目录
└── reimbursement.db          # SQLite数据库（自动生成）
```

## 系统说明

- 数据库使用SQLite，首次运行时自动创建
- 文件上传限制：50MB，支持PDF、图片、Word文档
- 申请编号格式：FB+日期+6位随机码（如：FB20231201A1B2C3）
- 系统采用响应式设计，支持移动端访问

## 日志功能

系统提供简洁的日志记录功能：

### 日志文件

- **应用日志** (`logs/app.log`)：统一记录所有操作和系统事件

### 记录内容

- 操作类型、用户身份、请求参数
- 执行结果（成功/失败+错误信息）
- 每个操作记录为单行日志，便于查看和分析

### 特点

- 日志自动轮转，单文件最大10MB，保留5个备份
- 统一格式，便于日志分析和监控

## 从单容器迁移到 Docker Compose

如果你之前使用单容器部署，可以按以下步骤迁移：

1. **备份数据**：

```bash
mkdir -p backup/$(date +%Y%m%d_%H%M%S)
cp -r uploads logs reimbursement.db backup/$(date +%Y%m%d_%H%M%S)/
```

2. **停止旧容器**：

```bash
docker stop invoice-app
docker rm invoice-app
```

3. **启动新架构**：

```bash
docker compose -f docker-compose.simple.yml up -d --build
```

## 故障排除

### 权限问题

如果遇到权限错误，确保目录权限正确：

```bash
sudo chown -R 1000:1000 uploads logs
chmod 755 uploads logs
```

### 容器无法启动

检查容器日志：

```bash
docker compose -f docker-compose.simple.yml logs web
```

### 端口冲突

如果5000端口被占用，修改 `.env` 文件：

```bash
WEB_PORT=5001
```

### 数据库连接问题

确保数据库文件存在且可读写：

```bash
ls -la reimbursement.db
```

## 技术栈

- 后端：Flask + SQLite/PostgreSQL
- 前端：Bootstrap 5 + Bootstrap Icons
- 数据导出：pandas + openpyxl
- 容器化：Docker + Docker Compose
- Web服务器：Gunicorn + Gevent
