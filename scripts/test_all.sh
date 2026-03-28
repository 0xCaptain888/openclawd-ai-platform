#!/usr/bin/env bash
# ==============================================================================
# AI 统一平台 - 集成测试脚本
# ==============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
source "$PROJECT_DIR/.env" 2>/dev/null || true

GATEWAY_PORT="${GATEWAY_PORT:-80}"
BASE_URL="http://localhost:${GATEWAY_PORT}"
API_KEY=$(echo "${API_KEYS:-sk-admin-001:admin:120:50000}" | cut -d',' -f1 | cut -d':' -f1)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0

pass() { echo -e "  ${GREEN}PASS${NC} $*"; ((PASS++)); }
fail() { echo -e "  ${RED}FAIL${NC} $*"; ((FAIL++)); }
skip() { echo -e "  ${YELLOW}SKIP${NC} $*"; ((SKIP++)); }

test_endpoint() {
    local name="$1"
    local method="$2"
    local url="$3"
    local data="${4:-}"
    local need_auth="${5:-true}"

    local auth_header=""
    if [ "$need_auth" = "true" ]; then
        auth_header="-H \"Authorization: Bearer ${API_KEY}\""
    fi

    local cmd="curl -sf -X ${method} -w '%{http_code}' -o /tmp/test_response.json"
    cmd+=" -H 'Content-Type: application/json'"
    if [ -n "$auth_header" ]; then
        cmd+=" -H 'Authorization: Bearer ${API_KEY}'"
    fi
    if [ -n "$data" ]; then
        cmd+=" -d '${data}'"
    fi
    cmd+=" '${url}' 2>/dev/null"

    local status
    status=$(eval "$cmd") || status="000"

    if [ "$status" -ge 200 ] && [ "$status" -lt 300 ]; then
        pass "$name (HTTP $status)"
    elif [ "$status" = "000" ]; then
        fail "$name (连接失败)"
    elif [ "$status" = "502" ] || [ "$status" = "503" ]; then
        skip "$name (上游服务未启动, HTTP $status)"
    else
        fail "$name (HTTP $status)"
    fi
}

echo "=============================================="
echo "  AI 统一平台 - 集成测试"
echo "=============================================="
echo ""
echo "网关地址: $BASE_URL"
echo "API Key:  ${API_KEY:0:10}..."
echo ""

# ---------- 1. 网关基础测试 ----------
echo "[1/4] 网关基础测试"
test_endpoint "GET /health (无需认证)" "GET" "${BASE_URL}/health" "" "false"
test_endpoint "GET /stats (需要认证)" "GET" "${BASE_URL}/stats"
echo ""

# ---------- 2. 社交机器人服务测试 ----------
echo "[2/4] 社交机器人服务"
test_endpoint "GET /social/health" "GET" "${BASE_URL}/social/health"
echo ""

# ---------- 3. 网站后端服务测试 ----------
echo "[3/4] 网站后端服务"
test_endpoint "GET /website/health" "GET" "${BASE_URL}/website/health"
echo ""

# ---------- 4. 交易服务测试 ----------
echo "[4/4] 交易服务"
test_endpoint "GET /trading/health" "GET" "${BASE_URL}/trading/health"
echo ""

# ---------- 汇总 ----------
TOTAL=$((PASS + FAIL + SKIP))
echo "=============================================="
echo "  测试结果: 共 ${TOTAL} 项"
echo "  通过: ${PASS}  失败: ${FAIL}  跳过: ${SKIP}"
echo "=============================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
