#!/bin/bash

# 骈聪课题组发票报销系统 - Docker Compose 部署脚本
# 使用方法: ./deploy.sh [start|stop|restart|logs|status|backup]

set -e

# 配置
COMPOSE_FILE="docker-compose.simple.yml"
SERVICE_NAME="web"
BACKUP_DIR="backup/$(date +%Y%m%d_%H%M%S)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Docker 和 Docker Compose
check_requirements() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不在 PATH 中"
        exit 1
    fi

    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装或不在 PATH 中"
        exit 1
    fi
}

# 备份数据
backup_data() {
    log_info "开始备份数据到 $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    if [ -f "reimbursement.db" ]; then
        cp reimbursement.db "$BACKUP_DIR/"
        log_success "数据库备份完成"
    fi
    
    if [ -d "uploads" ]; then
        cp -r uploads "$BACKUP_DIR/"
        log_success "上传文件备份完成"
    fi
    
    if [ -d "logs" ]; then
        cp -r logs "$BACKUP_DIR/"
        log_success "日志文件备份完成"
    fi
    
    log_success "数据备份完成: $BACKUP_DIR"
}

# 启动服务
start_service() {
    log_info "启动发票报销系统..."
    
    # 确保权限正确
    if [ -d "uploads" ] || [ -d "logs" ]; then
        log_info "修正文件权限..."
        sudo chown -R 1000:1000 uploads logs 2>/dev/null || true
        chmod 755 uploads logs 2>/dev/null || true
    fi
    
    docker compose -f "$COMPOSE_FILE" up -d --build
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 5
    
    # 检查服务状态
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_success "服务启动成功!"
        log_info "访问地址: http://localhost:5000"
        log_info "管理后台: http://localhost:5000/admin/login"
    else
        log_error "服务启动失败，请检查日志"
        docker compose -f "$COMPOSE_FILE" logs
        exit 1
    fi
}

# 停止服务
stop_service() {
    log_info "停止发票报销系统..."
    docker compose -f "$COMPOSE_FILE" down
    log_success "服务已停止"
}

# 重启服务
restart_service() {
    log_info "重启发票报销系统..."
    stop_service
    start_service
}

# 查看日志
show_logs() {
    log_info "显示服务日志..."
    docker compose -f "$COMPOSE_FILE" logs -f "$SERVICE_NAME"
}

# 查看状态
show_status() {
    log_info "服务状态:"
    docker compose -f "$COMPOSE_FILE" ps
    
    log_info "网络状态:"
    docker network ls | grep invoice || echo "未找到 invoice 网络"
    
    log_info "磁盘使用:"
    du -sh uploads logs reimbursement.db 2>/dev/null || echo "数据目录不存在"
}

# 显示帮助
show_help() {
    echo "骈聪课题组发票报销系统 - Docker Compose 部署脚本"
    echo ""
    echo "使用方法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start    启动服务"
    echo "  stop     停止服务"
    echo "  restart  重启服务"
    echo "  logs     查看日志"
    echo "  status   查看状态"
    echo "  backup   备份数据"
    echo "  help     显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 start     # 启动服务"
    echo "  $0 logs      # 查看实时日志"
    echo "  $0 backup    # 备份数据"
}

# 主函数
main() {
    check_requirements
    
    case "${1:-help}" in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
        backup)
            backup_data
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
