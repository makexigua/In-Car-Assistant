set -e

ROOT_DIR="$(cd "$(dirname --"$0")" && pwd)"
MAIN_DIR="$ROOT_DIR/main"
TASK_DIR="$ROOT_DIR/task"
KB_DIR="$ROOT_DIR/kb"

# 优先使用项目内虚拟环境；没有就回退到系统 python3。
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

# 不安装新包时，复用用户目录下已安装的依赖。
USER_SITE_PACKAGES="$(python3 -m site --user-site 2>/dev/null || true)"
if [ -n "$USER_SITE_PACKAGES" ]; then
  export PYTHONPATH="$USER_SITE_PACKAGES:$PYTHONPATH"
fi

# 本地链路都走 127.0.0.1，避免被全局 HTTP 代理劫持。
export NO_PROXY="127.0.0.1,localhost,::1${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"

mkdir -p "$MAIN_DIR/log"
mkdir -p "$KB_DIR/log"

# 说明：请先在 .env 配置好统一大模型参数（LLM_BASE_URL / LLM_API_KEY / DEFAULT_CHAT_MODEL）。
# FAQ 分支依赖的 RAG 服务如果是独立进程，也需要提前启动并配置 RAG_URL。

cp .env.example .env

# 入口服务 
cd "$MAIN_DIR"
PYTHONPATH="$ROOT_DIR:$MAIN_DIR:$TASK_DIR:$PYTHONPATH" nohup "$PYTHON_BIN" start.py > "$MAIN_DIR/log/start.log" 2>&1 &
echo "启动入口服务.."
sleep 5

echo "提示：请确保 RAG_URL 对应的知识库服务已启动（FAQ 分支会调用）"

echo "done"
