set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
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

# 说明：拒识服务和意图召回服务如果是外部服务，请先自行启动，
# 并在 .env 里配置好 REJECT_URL / INTENT_URL。

# 大模型nlu服务
cd "$TASK_DIR/function_call"
PYTHONPATH="$TASK_DIR:$MAIN_DIR:$PYTHONPATH" nohup "$PYTHON_BIN" chatnlu_infer.py > "$MAIN_DIR/log/nlu.log" 2>&1 &
echo "启动NLU服务.."
sleep 5

# 入口服务 
cd "$MAIN_DIR"
PYTHONPATH="$MAIN_DIR:$PYTHONPATH" nohup "$PYTHON_BIN" start.py > "$MAIN_DIR/log/start.log" 2>&1 &
echo "启动入口服务.."
sleep 5

echo "提示：请确保 RAG_URL 对应的知识库服务已启动（FAQ 分支会调用）"

echo "done"
