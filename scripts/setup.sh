#!/usr/bin/env bash
# ==============================================================================
# AI 统一平台 - 快速部署脚本
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------- 1. 检查 Docker 和 Docker Compose ----------
info "检查 Docker 环境..."
command -v docker >/dev/null 2>&1 || error "未找到 Docker，请先安装: https://docs.docker.com/get-docker/"

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    error "未找到 Docker Compose，请先安装: https://docs.docker.com/compose/install/"
fi

info "Docker 版本: $(docker --version)"
info "Compose 命令: $COMPOSE_CMD"

# ---------- 2. 复制 .env 配置文件 ----------
cd "$PROJECT_DIR"

if [ ! -f .env ]; then
    info "未检测到 .env 文件，从 .env.example 复制..."
    cp .env.example .env
    warn "请编辑 .env 文件，配置 LLM_API_URL 和 API 密钥等参数"
    warn "配置文件路径: $PROJECT_DIR/.env"
else
    info ".env 文件已存在，跳过复制"
fi

# ---------- 3. 创建必要目录 ----------
info "创建数据目录..."
mkdir -p "$PROJECT_DIR/data/gateway-logs"
mkdir -p "$PROJECT_DIR/data/social-bot"
mkdir -p "$PROJECT_DIR/data/website-backend"
mkdir -p "$PROJECT_DIR/data/trading"
mkdir -p "$PROJECT_DIR/data/redis"

# ---------- 4. 构建并启动所有服务 ----------
info "构建并启动所有服务..."
$COMPOSE_CMD build --parallel 2>/dev/null || $COMPOSE_CMD build
$COMPOSE_CMD up -d

# ---------- 5. 等待服务启动 ----------
info "等待服务启动..."
sleep 5

# ---------- 6. 健康检查 ----------
info "执行健康检查..."
GATEWAY_PORT=$(grep -oP 'GATEWAY_PORT=\K[0-9]+' .env 2>/dev/null || echo "80")
GATEWAY_URL="http://localhost:${GATEWAY_PORT}"

MAX_RETRIES=12
RETRY_INTERVAL=5
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf "${GATEWAY_URL}/health" >/dev/null 2>&1; then
        info "Gateway 健康检查通过!"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        warn "Gateway 未在预期时间内就绪，请检查日志: $COMPOSE_CMD logs gateway"
    else
        echo -n "."
        sleep $RETRY_INTERVAL
    fi
done

# ---------- 7. 打印访问信息 ----------
echo ""
echo "=============================================="
echo "  AI 统一平台部署完成"
echo "=============================================="
echo ""
info "服务访问地址:"
echo "  API Gateway:     ${GATEWAY_URL}"
echo "  健康检查:        ${GATEWAY_URL}/health"
echo "  使用统计:        ${GATEWAY_URL}/stats"
echo ""
info "代理路由:"
echo "  LLM API:         ${GATEWAY_URL}/v1/*"
echo "  社交机器人:      ${GATEWAY_URL}/social/*"
echo "  网站后端:        ${GATEWAY_URL}/website/*"
echo "  交易服务:        ${GATEWAY_URL}/trading/*"
echo ""
info "常用命令:"
echo "  查看日志:        $COMPOSE_CMD logs -f"
echo "  停止服务:        $COMPOSE_CMD down"
echo "  重启服务:        $COMPOSE_CMD restart"
echo "  查看状态:        $COMPOSE_CMD ps"
echo ""
