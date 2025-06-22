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

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 运行系统：

```bash
python app.py
```

3. 访问系统：

- 用户端：<http://localhost:5000>
- 管理后台：<http://localhost:5000/admin/login>

## 默认管理员账户

- 用户名：`admin`
- 密码：`admin123`

## 目录结构

```
fapiao/
├── app.py              # 主应用文件
├── requirements.txt    # Python依赖
├── templates/          # HTML模板
│   ├── base.html
│   ├── index.html
│   ├── success.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   └── admin_detail.html
├── uploads/           # 文件上传目录
├── logs/              # 日志文件目录（自动生成）
│   └── app.log        # 应用日志
└── reimbursement.db   # SQLite数据库（自动生成）
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

## 技术栈

- 后端：Flask + SQLite
- 前端：Bootstrap 5 + Bootstrap Icons
- 数据导出：pandas + openpyxl
