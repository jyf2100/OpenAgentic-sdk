#!/bin/bash
# Host 启动脚本
# 用法: ./scripts/start-host.sh [--dev]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[HOST]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[HOST]${NC} $1"; }
log_error() { echo -e "${RED}[HOST]${NC} $1"; }

# 默认配置
HOST="0.0.0.0"
PORT="${OA_HOST_PORT:-8766}"
REPO_ROOT="${OA_REPO_ROOT:-$(pwd)}"
SESSION_ROOT="${OA_SESSION_ROOT:-/tmp/openagentic-sessions}"
REMOTE_CONFIG="${OA_REMOTE_CONFIG:-${REPO_ROOT}/openagentic.remote.json}"
MODE="dev"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev|--production)
            MODE="${1#--}"
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --repo)
            REPO_ROOT="$2"
            shift 2
            ;;
        --session)
            SESSION_ROOT="$2"
            shift 2
            ;;
        --config)
            REMOTE_CONFIG="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --dev           开发模式 (默认)"
            echo "  --production     生产模式"
            echo "  --port <端口>    Host 端口 (默认: ${PORT})"
            echo "  --repo <路径>    代码仓库路径 (默认: ${REPO_ROOT})"
            echo "  --session <路径> 会话存储路径 (默认: ${SESSION_ROOT})"
            echo "  --config <文件>  远程配置文件 (默认: ${REMOTE_CONFIG})"
            echo "  --help, -h      显示帮助"
            echo ""
            echo "环境变量:"
            echo "  OA_HOST_PORT     Host 端口"
            echo "  OA_REPO_ROOT     代码仓库路径"
            echo "  OA_SESSION_ROOT  会话存储路径"
            echo "  OA_REMOTE_CONFIG 远程配置文件"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 检查前置条件
if [[ ! -d "${REPO_ROOT}" ]]; then
    log_error "仓库目录不存在: ${REPO_ROOT}"
    exit 1
fi

# 创建会话目录
mkdir -p "${SESSION_ROOT}"

# 构建 Worker URL 参数
WORKER_URLS=""
if [[ -n "${OA_WORKER_URLS}" ]]; then
    for url in ${OA_WORKER_URLS}; do
        WORKER_URLS="${WORKER_URLS} --node-url ${url}"
    done
elif [[ -f "${REMOTE_CONFIG}" ]]; then
    log_info "从配置文件读取 Worker 信息..."
    # 从配置文件中解析 node_name 并构建 URL
    # 这里需要假设 Worker 在 localhost 上运行
    WORKER_NODE_COUNT=$(grep -c '"node_name"' "${REMOTE_CONFIG}" 2>/dev/null || echo "0")
    if [[ "${WORKER_NODE_COUNT}" -gt 0 ]]; then
        WORKER_PORT="${OA_WORKER_BASE_PORT:-19000}"
        for i in $(seq 0 $((WORKER_NODE_COUNT - 1))); do
            WORKER_URLS="${WORKER_URLS} --node-url node-$i=http://localhost:$((WORKER_PORT + i))"
        done
    fi
fi

# 显示启动信息
echo ""
log_info "========================================"
log_info "  OpenAgentic SDK - Host 启动"
log_info "========================================"
echo ""
log_info "模式:      ${MODE}"
log_info "监听地址:  ${HOST}:${PORT}"
log_info "仓库路径:  ${REPO_ROOT}"
log_info "会话存储:  ${SESSION_ROOT}"
log_info "配置文件:  ${REMOTE_CONFIG}"
if [[ -n "${WORKER_URLS}" ]]; then
    log_info "Workers:    已配置"
else
    log_warn "Workers:    未配置 (无 --node-url)"
fi
echo ""

# 检查必要环境变量
if [[ -z "${ANTHROPIC_API_KEY}" ]] && [[ -z "${OPENAI_API_KEY}" ]]; then
    log_warn "未设置 LLM API Key 环境变量 (ANTHROPIC_API_KEY 或 OPENAI_API_KEY)"
fi

# 启动 Host
cd "${REPO_ROOT}"
exec python -m openagentic_sdk.server.cluster_chat_host \
    --host "${HOST}" \
    --port "${PORT}" \
    --repo-root "${REPO_ROOT}" \
    --session-root "${SESSION_ROOT}" \
    ${WORKER_URLS} \
    ${REMOTE_CONFIG:+--remote-config "${REMOTE_CONFIG}"} \
    ${OA_PROVIDER_FACTORY:+--provider-factory "${OA_PROVIDER_FACTORY}"} \
    ${OA_MODEL:+--model "${OA_MODEL}"}
