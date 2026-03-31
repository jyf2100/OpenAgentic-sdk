#!/bin/bash
# 启动 Host + 所有 Worker
# 用法: ./scripts/start-all.sh

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[HOST]${NC} $1"; }
log_node() { echo -e "${BLUE}[WORKER ${1}]${NC} $2"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SESSION_ROOT="${OA_SESSION_ROOT:-/tmp/openagentic-sessions}"
HOST_PORT="${OA_HOST_PORT:-8766}"
WORKER_BASE_PORT="${OA_WORKER_BASE_PORT:-19000}"

# 默认 Worker 配置
WORKERS=(
    "agent-0"
    "agent-1"
)

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --workers)
            shift
            WORKERS=()
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                WORKERS+=("$1")
                shift
            done
            ;;
        --host-port)
            HOST_PORT="$2"
            shift 2
            ;;
        --no-host)
            NO_HOST=true
            shift
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --workers <节点1> [节点2] ...  Worker 节点列表 (默认: agent-0 agent-1)"
            echo "  --host-port <端口>            Host 端口 (默认: ${HOST_PORT})"
            echo "  --no-host                    只启动 Workers，不启动 Host"
            echo "  --help, -h                   显示帮助"
            echo ""
            echo "环境变量:"
            echo "  OA_HOST_PORT        Host 端口"
            echo "  OA_WORKER_BASE_PORT Worker 起始端口"
            echo "  OA_SESSION_ROOT     会话存储路径"
            echo "  OA_REPO_ROOT        代码仓库路径"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 设置 trap 确保清理
cleanup() {
    echo ""
    log_info "正在停止所有进程..."
    for pid in "${WORKER_PIDS[@]}"; do
        kill "${pid}" 2>/dev/null || true
    done
    if [[ -n "${HOST_PID}" ]]; then
        kill "${HOST_PID}" 2>/dev/null || true
    fi
    log_info "已停止所有进程"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 创建会话目录
mkdir -p "${SESSION_ROOT}"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  OpenAgentic SDK - 一键启动${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 构建 Worker URL 参数
WORKER_URLS=""
for i in "${!WORKERS[@]}"; do
    NODE="${WORKERS[$i]}"
    PORT=$((WORKER_BASE_PORT + i))
    WORKER_URLS="${WORKER_URLS} --node-url ${NODE}=http://localhost:${PORT}"
done

# 启动 Workers
declare -a WORKER_PIDS
log_info "启动 ${#WORKERS[@]} 个 Worker 节点..."

for i in "${!WORKERS[@]}"; do
    NODE="${WORKERS[$i]}"
    PORT=$((WORKER_BASE_PORT + i))

    (
        cd "${REPO_ROOT}"
        exec python -m openagentic_sdk.subagents.remote_http_worker_server \
            --host 0.0.0.0 \
            --port "${PORT}" \
            --repo-root "${REPO_ROOT}" \
            --session-root "${SESSION_ROOT}" \
            --node-name "${NODE}" \
            --remote-config "${REPO_ROOT}/openagentic.remote.json"
    ) &

    WORKER_PIDS+=($!)
    log_node "${NODE}" "启动中 (端口: ${PORT}, PID: ${WORKER_PIDS[-1]})"
done

# 等待 Workers 就绪
sleep 3

# 检查 Workers 状态
for i in "${!WORKERS[@]}"; do
    NODE="${WORKERS[$i]}"
    PORT=$((WORKER_BASE_PORT + i))

    if curl -sf -m 2 "http://localhost:${PORT}/health" > /dev/null 2>&1; then
        log_node "${NODE}" "${GREEN}✓ 就绪${NC} (http://localhost:${PORT})"
    else
        log_node "${NODE}" "${YELLOW}⚠ 健康检查失败${NC} - 可能仍在启动"
    fi
done

echo ""

# 启动 Host
if [[ -z "${NO_HOST}" ]]; then
    log_info "启动 Host..."

    (
        cd "${REPO_ROOT}"
        exec python -m openagentic_sdk.server.cluster_chat_host \
            --host 0.0.0.0 \
            --port "${HOST_PORT}" \
            --repo-root "${REPO_ROOT}" \
            --session-root "${SESSION_ROOT}" \
            ${WORKER_URLS} \
            --remote-config "${REPO_ROOT}/openagentic.remote.json"
    ) &

    HOST_PID=$!
    log_info "Host 启动中 (端口: ${HOST_PORT}, PID: ${HOST_PID})"

    sleep 2

    if curl -sf -m 2 "http://localhost:${HOST_PORT}/health" > /dev/null 2>&1; then
        log_info "${GREEN}✓ 就绪${NC} (http://localhost:${HOST_PORT})"
    else
        log_info "${YELLOW}⚠ Host 健康检查失败${NC} - 可能仍在启动"
    fi
fi

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  启动完成${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
log_info "Workers:"
for i in "${!WORKERS[@]}"; do
    NODE="${WORKERS[$i]}"
    PORT=$((WORKER_BASE_PORT + i))
    echo -e "  ${BLUE}${NODE}${NC}:  http://localhost:${PORT}"
done
if [[ -z "${NO_HOST}" ]]; then
    echo ""
    log_info "Host:"
    echo -e "  ${GREEN}API${NC}:       http://localhost:${HOST_PORT}"
    echo -e "  ${GREEN}Health${NC}:    http://localhost:${HOST_PORT}/health"
    echo -e "  ${GREEN}Sessions${NC}:  http://localhost:${HOST_PORT}/session"
fi
echo ""
log_info "按 Ctrl+C 停止所有服务"
echo ""

# 保持运行
wait
