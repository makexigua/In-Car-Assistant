"""
MCP 执行器 — 智能代理模式。

核心改进：
  1. list_tools 返回的工具定义保留原始 name/description/parameters，
     额外叠加项目级 recall_keywords（仅用于规则召回，不影响 LLM）
  2. LLM 选工具 → 智能参数预处理（如地名→坐标） → call_tool
  3. 熔断 + 指数退避重试 + 健康检查 → 稳定性保障
  4. 惰性初始化 → 无模块级副作用
"""

import asyncio
import json
import re
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
# MCP 工具描述增强 — 解决规则召回阶段 MCP 工具与用户口语零匹配的问题
# 注：只叠加 recall_keywords，不覆盖 MCP server 原始 description
# ================================================================

MCP_TOOL_KEYWORDS: Dict[str, str] = {
    "maps_direction_driving": "导航 开车 驾车 路线 怎么去 到 前往 去 目的地 路线规划 到达 行驶 路程 导航去 开车去",
    "maps_weather": "天气 温度 下雨 下雪 晴天 阴天 刮风 降温 升温 天气预报 气温 雨 雪 风 雾霾 湿度",
    "maps_text_search": "搜索 查找 找 哪里有 推荐 景点 餐厅 酒店 商场 美食 医院 加油站 停车场 厕所 银行",
    "maps_search_detail": "详情 详细信息 电话 地址 营业时间 评价 评分 介绍 怎么样",
    "maps_around_search": "附近 周围 周边 就近 旁边的 最近 靠近",
    "maps_geo": "坐标 经纬度 地址转换 地理位置 地址解析 转坐标 在哪里",
    "maps_regeocode": "逆地理 坐标转地址 经纬度转地址 这个位置在哪",
    "maps_bicycling": "骑行 自行车 骑车 单车 骑行路线",
    "maps_direction_walking": "步行 走路 徒步 步行路线 走过去",
    "maps_direction_transit_integrated": "公交 地铁 怎么坐车 公共交通 乘车路线 坐公交 坐地铁 公交路线",
    "maps_ip_location": "IP定位 我的位置 当前位置 我在哪 定位",
    "maps_distance": "距离 多远 多远距离 测量距离 相距",
}


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
_known_mcp_tool_schemas: dict[str, dict] = {}
_circuit_breaker = CircuitBreaker(
    threshold=MCP_CIRCUIT_BREAKER_THRESHOLD,
    recovery_timeout=MCP_RECOVERY_TIMEOUT,
)


# ================================================================
# MCP 工具 → OpenAI 格式（增强）
# ================================================================


def _mcp_tool_to_openai(mcp_tool: Any) -> Dict[str, Any]:
    """MCP Tool → OpenAI function calling 格式。

    保留 MCP server 原始的 name / description / parameters，
    额外叠加项目级的 recall_keywords 以提升规则召回阶段的命中率。
    """
    name = mcp_tool.name
    description = mcp_tool.description or ""
    recall_keywords = MCP_TOOL_KEYWORDS.get(name, "")

    tool_dict: Dict[str, Any] = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": mcp_tool.inputSchema,
        },
    }
    if recall_keywords:
        tool_dict["recall_keywords"] = recall_keywords
    return tool_dict


# ================================================================
# 智能参数预处理 — 地名 → 坐标解析
# ================================================================

# 需要将地名解析为坐标的工具及其参数映射
_GEO_RESOLVE_MAP: Dict[str, list[str]] = {
    "maps_direction_driving": ["destination", "origin"],
    "maps_bicycling": ["destination", "origin"],
    "maps_direction_walking": ["destination", "origin"],
    "maps_direction_transit_integrated": ["destination", "origin"],
    "maps_distance": ["destination", "origin"],
}


def _is_coordinate(value: str) -> bool:
    """判断字符串是否为"经度,纬度"格式的坐标。"""
    value = (value or "").strip()
    # 匹配 数字,数字 格式的坐标
    return bool(re.match(r"^-?\d+\.?\d*,\s*-?\d+\.?\d*$", value))


def _needs_geo_resolve(value: Any) -> bool:
    """判断一个参数值是否需要通过地理编码解析（不是坐标格式的字符串即需要解析）。"""
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value:
        return False
    return not _is_coordinate(value)


async def _resolve_place_to_coords(
    client: MCPClient,
    place_name: str,
) -> Optional[str]:
    """通过 maps_geo 将地名解析为"经度,纬度"字符串。"""
    if not place_name:
        return None
    try:
        raw = await client.call_tool(
            "maps_geo",
            {"address": place_name},
            timeout=MCP_CALL_TIMEOUT,
        )
        text = client.extract_text(raw)
        result = json.loads(text) if isinstance(text, str) else text
        if isinstance(result, list) and len(result) > 0:
            location = result[0].get("location", "")
            if location:
                logger.info("[MCP] 地理编码: %s → %s", place_name, location)
                return location
        logger.warning("[MCP] 地理编码 %s 无结果: %s", place_name, text)
        return None
    except Exception as e:
        logger.warning("[MCP] 地理编码失败 %s: %s", place_name, e)
        return None


def _lists_known_mcp_schemas() -> dict[str, dict]:
    """返回已注册 MCP 工具的原始 schema 映射（来自 list_tools 的原始定义）。"""
    return _known_mcp_tool_schemas


async def _resolve_tool_arguments(
    function_name: str,
    arguments: Dict[str, Any],
    client: MCPClient,
) -> Dict[str, Any]:
    """智能解析工具参数：将地名转为坐标，补充合理默认值。

    当前支持的解析：
    - maps_direction_driving 等导航类工具：destination/origin 中地名 → maps_geo 解析为坐标
    - 未指定 origin 时不补充（由 MCP 服务端处理，它默认用当前定位）
    """
    resolved = dict(arguments)

    # 只对已知需要地理解析的工具进行处理
    geo_params = _GEO_RESOLVE_MAP.get(function_name)
    if not geo_params:
        return resolved

    for param in geo_params:
        raw_value = resolved.get(param)
        if raw_value is None or raw_value == "":
            continue
        if _needs_geo_resolve(raw_value):
            coords = await _resolve_place_to_coords(client, str(raw_value))
            if coords:
                resolved[param] = coords

    return resolved


# ================================================================
# 公开 API
# ================================================================


def init_mcp() -> bool:
    """初始化：连接 MCP Server → list_tools → 注册到 FUNCTION_TOOLS。

    幂等，多次调用只执行一次。
    """
    global _mcp_client, _initialized, _mcp_function_names, _known_mcp_tool_schemas

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

        # 保存原始 schema 供内部使用（如地理编码）
        _known_mcp_tool_schemas = {t.name: t.inputSchema for t in discovered_tools}

        # 增强后注册：叠加中文描述 + recall_keywords
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
        logger.error("[MCP] 初始化失败: %s (%s)", err, type(err).__name__)
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
# 异步重试执行（带智能参数预处理）
# ================================================================


async def _call_with_retry_async(
    function_name: str,
    client: MCPClient,
    arguments: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """带指数退避重试的 call_tool。在调用前先做智能参数预处理。"""
    command = AMAP_MCP_COMMAND
    args = AMAP_MCP_ARGS or []
    env = {"AMAP_MAPS_API_KEY": AMAP_MAPS_API_KEY} if AMAP_MAPS_API_KEY else {}

    # 智能参数预处理：地名 → 坐标、补充默认值等
    resolved_args = await _resolve_tool_arguments(function_name, arguments, client)

    for attempt in range(MCP_RETRY_MAX + 1):
        try:
            if attempt > 0:
                healthy = await client.health_check()
                if not healthy:
                    logger.warning("[MCP] 健康检查失败，尝试重连 (attempt %d)", attempt + 1)
                    await client.reconnect(command, args, env, timeout=MCP_CONNECT_TIMEOUT)

            # --- 智能转发：参数已经过预处理 ---
            raw = await client.call_tool(function_name, resolved_args, timeout=MCP_CALL_TIMEOUT)
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
    """执行 MCP 工具（带智能参数预处理）。

    熔断检查 → 惰性初始化 → 参数智能解析 → 指数退避重试 → call_tool。
    """
    # 1. 熔断检查
    if not _circuit_breaker.allow_request():
        logger.warning("[MCP] 熔断器 OPEN，快速拒绝 %s", function_name)
        return {"tool": {"error": "MCP 服务暂不可用（熔断中）"}}

    # 2. 惰性初始化
    if not _initialized or _mcp_client is None:
        if not init_mcp():
            return {"tool": {"error": "MCP 未初始化"}}

    # 3. 智能执行（参数预处理 + 重试）
    bridge = _get_bridge()
    return bridge.run(
        _call_with_retry_async(function_name, _mcp_client, slots),
        timeout=(MCP_CALL_TIMEOUT + 1.0) * (MCP_RETRY_MAX + 1) + 10.0,
    )
