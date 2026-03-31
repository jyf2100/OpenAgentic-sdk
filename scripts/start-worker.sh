#!/bin/bash
# Worker 启动脚本
# 用法: ./scripts/start-worker.sh --node <节点名> [--dev]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[WORKER]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WORKER]${NC} $1"; }
log_error() { echo -e "${RED}[WORKER]${NC} $1"; }
log_node() { echo -e "${BLUE}[NODE ${1}]${NC} $2"; }

# 默认配置
HOST="0.0.0.0"
PORT="${OA_WORKER_PORT:-19000}"
NODE_NAME=""
REPO_ROOT="${OA_REPO_ROOT:-/workspace/repo}"
SESSION_ROOT="${OA_SESSION_ROOT:-/tmp/openagentic-sessions}"
REMOTE_CONFIG="${OA_REMOTE_CONFIG:-${REPO_ROOT}/openagentic.remote.json}}"
MODE="dev"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --node|-n)
            NODE_NAME="$2"
            shift 2
            ;;
        --dev|--production)
            MODE="${1#--}"
            shift
            ;;
        --port|-p)
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
        --config|-c)
            REMOTE_CONFIG="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 --node <节点名> [选项]"
            echo ""
            echo "必需参数:"
            echo "  --node, -n <名称>  节点唯一标识 (如: agent-0, research-node)"
            echo ""
            echo "选项:"
            echo "  --dev              开发模式 (默认)"
            echo "  --production       生产模式"
            echo "  --port, -p <端口>  Worker 端口 (默认: ${PORT})"
            echo "  --repo <路径>      代码仓库路径 (默认: ${REPO_ROOT})"
            echo "  --session <路径>   会话存储路径 (默认: ${SESSION_ROOT})"
            echo "  --config, -c <文件> 远程配置文件 (默认: ${REMOTE_CONFIG})"
            echo "  --help, -h         显示帮助"
            echo ""
            echo "环境变量:"
            echo "  OA_WORKER_PORT     Worker 端口"
            echo "  OA_REPO_ROOT       代码仓库路径"
            echo "  OA_SESSION_ROOT    会话存储路径"
            echo "  OA_REMOTE_CONFIG   远程配置文件"
            echo ""
            echo "示例:"
            echo "  $0 --node agent-0 --port 19000"
            echo "  OA_WORKER_PORT=19001 $0 --node agent-1"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 检查必需参数
if [[ -z "${NODE_NAME}" ]]; then
    log_error "缺少必需参数: --node <节点名>"
    echo "使用 --help 查看帮助"
    exit 1
fi

# 检查仓库目录
if [[ ! -d "${REPO_ROOT}" ]]; then
    log_warn "仓库目录不存在: ${REPO_ROOT}"
    log_warn "如果 Worker 无法访问代码仓库，将无法使用项目 skills"
fi

# 创建会话目录
mkdir -p "${SESSION_ROOT}"

# 显示启动信息
echo ""
log_info "========================================"
log_info "  OpenAgentic SDK - Worker 启动"
log_info "========================================"
echo ""
log_node "${NODE_NAME}" "节点名称:   ${NODE_NAME}"
log_node "${NODE_NAME}" "监听地址:   ${HOST}:${PORT}"
log_node "${NODE_NAME}" "仓库路径:   ${REPO_ROOT}"
log_node "${NODE_NAME}" "会话存储:   ${SESSION_ROOT}"
log_node "${NODE_NAME}" "配置文件:   ${REMOTE_CONFIG}"
log_node "${NODE_NAME}" "模式:       ${MODE}"
echo ""

# 检查必要环境变量 (LLM API)
if [[ -z "${ANTHROPIC_API_KEY}" ]] && [[ -z "${OPENAI_API_KEY}" ]] && [[ -z "${RIGHTCODE_API_KEY}" ]]; then
    log_warn "未设置 LLM API Key 环境变量"
    log_warn "如果配置文件未包含 provider，此 Worker 将无法执行任务"
fi

# 健康检查函数
check_health() {
    local max_attempts=30
    local attempt=1
    log_node "${NODE_NAME}" "等待服务就绪..."

    while [[ ${attempt} -le ${max_attempts} ]]; do
        if curl -sf -m 2 "http://localhost:${PORT}/health" > /dev/null 2>&1; then
            log_node "${NODE_NAME}" "服务已就绪 (尝试 ${attempt}/${max_attempts})"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    log_error "服务启动超时"
    return 1
}

# 启动 Worker
cd "${REPO_ROOT}"
python -m openagentic_sdk.subagents.remote_http_worker_server \
    --host "${HOST}" \
    --port "${PORT}" \
    --repo-root "${REPO_ROOT}" \
    --session-root "${SESSION_ROOT}" \
    --node-name "${NODE_NAME}" \
    ${REMOTE_CONFIG:+--remote-config "${REMOTE_CONFIG}"} \
    ${OA_PROVIDER_FACTORY:+--provider-factory "${OA_PROVIDER_FACTORY}"} \
    ${OA_MODEL:+--model "${OA_MODEL}"} &

WORKER_PID=$!

# 等待健康检查
sleep 2

if check_health; then
    log_node "${NODE_NAME}" "Worker 启动成功 (PID: ${WORKER_PID})"
    log_node "${NODE_NAME}" "HTTP 端点: http://localhost:${PORT}"
    echo ""

    # 捕获退出信号
    trap "log_node ${NODE_NAME} '收到退出信号，正在关闭...'; kill ${WORKER_PID} 2>/dev/null; exit 0" SIGINT SIGTERM

    # 保持运行
    wait ${WORKER_PID}
else
    log_error "Worker 启动失败"
    exit 1
fi
