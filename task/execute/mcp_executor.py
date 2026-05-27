"""
MCP 执行器 — 纯代理模式。

工业界标准做法：
  1. list_tools 返回的工具定义直通 FUNCTION_TOOLS（不改名，不改参数）
  2. LLM 选工具 → call_tool 直通 MCP Server（无中间业务逻辑）
  3. 熔断 + 指数退避重试 + 健康检查 → 稳定性保障
  4. 惰性初始化 → 无模块级副作用
"""

import asyncio
import json
import threading
import time
from typing import Any, Dict, Optional

from main.utils import logger
from task.execute.function_registry import register_mcp_tools
from task.execute.mcp_client import MCPClient
from task.settings import (
    AMAP_MCP_ARGS,
    AMAP_MCP_COMMAND,
    AMAP_MAPS_API_KEY,
    MCP_CONNECT_TIMEOUT,
    MCP_CALL_TIMEOUT,
    MCP_RETRY_MAX,
    MCP_CIRCUIT_BREAKER_THRESHOLD,
    MCP_RECOVERY_TIMEOUT,
)

# ================================================================
# 异步桥接 — 专用线程 + 事件循环
# ================================================================


class _AsyncBridge:
    """专用 daemon 线程持有独立事件循环，用于 sync → async 桥接。"""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name="mcp-async-bridge",
        )
        self._thread.start()

    def run(self, coro, timeout: Optional[float] = None) -> Any:
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)


_bridge: Optional[_AsyncBridge] = None


def _get_bridge() -> _AsyncBridge:
    global _bridge
    if _bridge is None:
        _bridge = _AsyncBridge()
    return _bridge


# ================================================================
# 熔断器
# ================================================================


class _CircuitState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """熔断器 — 连续失败超过阈值后快速拒绝请求。"""

    def __init__(self, threshold: int = 3, recovery_timeout: float = 30.0):
        self.threshold = threshold
        self.recovery_timeout = recovery_timeout
        self._state = _CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._lock = threading.Lock()
        self.total_calls = 0
        self.failed_calls = 0

    @property
    def state(self) -> str:
        return self._state

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == _CircuitState.CLOSED:
                return True
            if self._state == _CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = _CircuitState.HALF_OPEN
                    logger.info("[MCP] 熔断器 HALF_OPEN，允许探测请求")
                    return True
                return False
            return True

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = _CircuitState.CLOSED
            self.total_calls += 1

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            self.total_calls += 1
            self.failed_calls += 1
            if self._failure_count >= self.threshold:
                self._state = _CircuitState.OPEN
                logger.warning(
                    "[MCP] 熔断器 OPEN（连续 %d 次失败，共失败 %d/%d 次）",
                    self.threshold,
                    self.failed_calls,
                    self.total_calls,
                )

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "total_calls": self.total_calls,
                "failed_calls": self.failed_calls,
                "failure_rate": round(self.failed_calls / max(self.total_calls, 1), 4),
            }


# ================================================================
# 全局状态
# ================================================================

_mcp_client: Optional[MCPClient] = None
_initialized = False
_mcp_function_names: set[str] = set()
_circuit_breaker = CircuitBreaker(
    threshold=MCP_CIRCUIT_BREAKER_THRESHOLD,
    recovery_timeout=MCP_RECOVERY_TIMEOUT,
)


# ================================================================
# MCP 工具 → OpenAI 格式（直通，不改名）
# ================================================================


def _mcp_tool_to_openai(mcp_tool: Any) -> Dict[str, Any]:
    """MCP Tool → OpenAI function calling 格式。

    保持原始 name / description / inputSchema，不做任何映射。
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        },
    }


# ================================================================
# 公开 API
# ================================================================


def init_mcp() -> bool:
    """初始化：连接 MCP Server → list_tools → 注册到 FUNCTION_TOOLS。

    幂等，多次调用只执行一次。
    """
    global _mcp_client, _initialized, _mcp_function_names

    if _initialized:
        return True

    command = AMAP_MCP_COMMAND
    if not command:
        logger.warning("[MCP] AMAP_MCP_COMMAND 为空，跳过初始化")
        return False

    try:
        client = MCPClient()
        bridge = _get_bridge()
        env = {"AMAP_MAPS_API_KEY": AMAP_MAPS_API_KEY} if AMAP_MAPS_API_KEY else {}

        discovered_tools = bridge.run(
            client.connect(
                command=command,
                args=AMAP_MCP_ARGS or [],
                env=env,
                timeout=MCP_CONNECT_TIMEOUT,
            ),
            timeout=MCP_CONNECT_TIMEOUT + 5.0,
        )
        _mcp_client = client

        # 直通：list_tools 返回什么就注册什么
        openai_tools = [_mcp_tool_to_openai(t) for t in discovered_tools]
        register_mcp_tools(openai_tools)
        _mcp_function_names = {t.name for t in discovered_tools}

        _initialized = True
        logger.info(
            "[MCP] 初始化完成，注册 %d 个工具: %s",
            len(openai_tools),
            sorted(_mcp_function_names),
        )
        return True

    except Exception as err:
        logger.error("[MCP] 初始化失败: %s", err)
        return False


def is_mcp_function(function_name: str) -> bool:
    return function_name in _mcp_function_names


def get_mcp_metrics() -> Dict[str, Any]:
    return {
        "initialized": _initialized,
        "connected": _mcp_client.is_connected if _mcp_client else False,
        "circuit_breaker": _circuit_breaker.metrics(),
        "registered_tools": sorted(_mcp_function_names),
    }


# ================================================================
# 异步重试执行（纯代理）
# ================================================================


async def _call_with_retry_async(
    function_name: str,
    client: MCPClient,
    arguments: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """带指数退避重试的 call_tool 纯转发。"""
    command = AMAP_MCP_COMMAND
    args = AMAP_MCP_ARGS or []
    env = {"AMAP_MAPS_API_KEY": AMAP_MAPS_API_KEY} if AMAP_MAPS_API_KEY else {}

    for attempt in range(MCP_RETRY_MAX + 1):
        try:
            if attempt > 0:
                healthy = await client.health_check()
                if not healthy:
                    logger.warning("[MCP] 健康检查失败，尝试重连 (attempt %d)", attempt + 1)
                    await client.reconnect(command, args, env, timeout=MCP_CONNECT_TIMEOUT)

            # --- 纯转发：不做任何业务逻辑 ---
            raw = await client.call_tool(function_name, arguments, timeout=MCP_CALL_TIMEOUT)
            text = client.extract_text(raw)
            result = _try_parse_json(text)

            _circuit_breaker.record_success()
            return {"tool": result}

        except Exception as err:
            logger.error(
                "[MCP] 调用 %s 失败 (attempt %d/%d): %s",
                function_name,
                attempt + 1,
                MCP_RETRY_MAX + 1,
                err,
            )
            if attempt < MCP_RETRY_MAX:
                await asyncio.sleep(1.0 * (2**attempt))

    _circuit_breaker.record_failure()
    return {
        "tool": {
            "error": f"MCP 调用失败: {function_name}（已重试 {MCP_RETRY_MAX} 次）",
        }
    }


def _try_parse_json(text: str) -> Any:
    """尝试 JSON 解析，失败返回原字符串。"""
    if not isinstance(text, str):
        return text
    raw = text.strip()
    if not raw:
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


# ================================================================
# 同步执行入口
# ================================================================


def execute_mcp_function(
    function_name: str,
    slots: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """执行 MCP 工具（纯代理）。

    熔断检查 → 惰性初始化 → 指数退避重试 → call_tool → 原样返回。
    """
    # 1. 熔断检查
    if not _circuit_breaker.allow_request():
        logger.warning("[MCP] 熔断器 OPEN，快速拒绝 %s", function_name)
        return {"tool": {"error": "MCP 服务暂不可用（熔断中）"}}

    # 2. 惰性初始化
    if not _initialized or _mcp_client is None:
        if not init_mcp():
            return {"tool": {"error": "MCP 未初始化"}}

    # 3. 纯代理执行
    bridge = _get_bridge()
    return bridge.run(
        _call_with_retry_async(function_name, _mcp_client, slots),
        timeout=(MCP_CALL_TIMEOUT + 1.0) * (MCP_RETRY_MAX + 1),
    )
