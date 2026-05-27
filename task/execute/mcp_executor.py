# 作用：执行地图与天气等远端 MCP Server 能力（天气/POI搜索/POI详情/附近搜索/公交路径/驾车路径）。

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from sinan import Sinan

from main.utils import logger
from task.execute.mcp_client import MCPClient
from task.settings import (
    AMAP_MCP_AROUND_TOOL,
    AMAP_MAPS_API_KEY,
    AMAP_MCP_ARGS,
    AMAP_MCP_COMMAND,
    AMAP_MCP_DRIVING_TOOL,
    AMAP_MCP_POI_TOOL,
    AMAP_MCP_SEARCH_DETAIL_TOOL,
    AMAP_MCP_TRANSIT_TOOL,
    AMAP_MCP_WEATHER_TOOL,
)


MCP_FUNCTIONS = {
    "Query_Weather",
    "Search_POI",
    "Search_Around_POI",
    "Search_POI_Detail",
    "Route_Transit_Integrated",
    "Route_Driving",
}


def is_mcp_function(function_name: str) -> bool:
    return function_name in MCP_FUNCTIONS


def _safe_json_loads(text: Any) -> Any:
    if isinstance(text, (dict, list)):
        return text
    if not isinstance(text, str):
        return text
    raw = text.strip()
    if not raw:
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


async def _call_mcp_tool_by_spec(
    command: Optional[str],
    args: Optional[list],
    env: Optional[Dict[str, str]],
    function_name: str,
    tool_args: Dict[str, Any],
) -> Any:
    """
    统一 MCP 调用入口（仅远端命令式）。
    未配置 command 直接抛错，避免误以为还在走本地 server。
    """
    if not command:
        raise ValueError("AMAP_MCP_COMMAND 为空，无法连接远端 MCP Server")

    client = MCPClient()
    try:
        await client.connect_to_server(command=command, args=args or [], env=env or {})
        response_text = await client.execute(function_name, tool_args)
        return _safe_json_loads(response_text)
    finally:
        await client.cleanup()


def _run_async(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError as err:
        if "asyncio.run() cannot be called from a running event loop" not in str(err):
            raise
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _extract_location_from_text_search_result(raw_result: Any) -> str:
    """
    从 maps_text_search 返回里提取第一个 POI 的经纬度 location。
    兼容常见字段结构，提取失败返回空串。
    """
    if not isinstance(raw_result, dict):
        return ""
    pois = raw_result.get("pois")
    if not isinstance(pois, list) or not pois:
        return ""
    first = pois[0]
    if not isinstance(first, dict):
        return ""
    location = str(first.get("location", "")).strip()
    return location


def _extract_poi_id_from_text_search_result(raw_result: Any) -> str:
    """从 maps_text_search 返回里提取第一个 POI 的 id。"""
    if not isinstance(raw_result, dict):
        return ""
    pois = raw_result.get("pois")
    if not isinstance(pois, list) or not pois:
        return ""
    first = pois[0]
    if not isinstance(first, dict):
        return ""
    poi_id = str(first.get("id", "")).strip()
    return poi_id


def _resolve_address_to_location(address: str, city: str, amap_env: Dict[str, str]) -> str:
    """
    把自然语言地址解析成经纬度字符串（lng,lat）。
    方案：复用 maps_text_search 找首个候选 POI。
    """
    keyword = (address or "").strip()
    if not keyword:
        return ""
    tool_args: Dict[str, Any] = {"keywords": keyword}
    if city:
        tool_args["city"] = city

    search_result = _run_async(
        _call_mcp_tool_by_spec(
            command=AMAP_MCP_COMMAND or None,
            args=AMAP_MCP_ARGS,
            env=amap_env,
            function_name=AMAP_MCP_POI_TOOL,
            tool_args=tool_args,
        )
    )
    return _extract_location_from_text_search_result(search_result)


def execute_mcp_function(function_name: str, slots: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    amap_env = {"AMAP_MAPS_API_KEY": AMAP_MAPS_API_KEY} if AMAP_MAPS_API_KEY else {}

    if function_name == "Query_Weather":
        city = str(slots.get("city", "北京") or "北京")
        date = str(slots.get("date", "")).strip()
        if date:
            try:
                date_parsed = Sinan(date).parse()
                if "datetime" in date_parsed:
                    date = date_parsed["datetime"][0].split(" ")[0]
            except Exception as err:
                logger.error(f"weather date parse failed: {err}")
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        tool_response = _run_async(
            _call_mcp_tool_by_spec(
                command=AMAP_MCP_COMMAND or None,
                args=AMAP_MCP_ARGS,
                env=amap_env,
                function_name=AMAP_MCP_WEATHER_TOOL,
                tool_args={"city": city, "date": date},
            )
        )
        return {"tool": tool_response}

    if function_name == "Search_POI":
        keyword = str(slots.get("keywords", "")).strip()
        if not keyword:
            # 兼容旧槽位写法，避免 prompt 轻微漂移导致无法命中。
            keyword_parts = []
            for key in ("city", "landmark", "POI"):
                value = str(slots.get(key, "")).strip()
                if value:
                    keyword_parts.append(value)
            keyword = "".join(keyword_parts).strip() or "附近"

        tool_args: Dict[str, Any] = {"keywords": keyword}
        city_value = str(slots.get("city", "")).strip()
        if city_value:
            tool_args["city"] = city_value

        tool_response = _run_async(
            _call_mcp_tool_by_spec(
                command=AMAP_MCP_COMMAND or None,
                args=AMAP_MCP_ARGS,
                env=amap_env,
                function_name=AMAP_MCP_POI_TOOL,
                tool_args=tool_args,
            )
        )
        return {"tool": tool_response}

    if function_name == "Search_Around_POI":
        center_keyword = str(slots.get("center", "")).strip()
        around_keyword = str(slots.get("keywords", "")).strip() or "美食"
        city = str(slots.get("city", "")).strip()
        radius = str(slots.get("radius", "")).strip() or "2000"

        if not center_keyword:
            return {"tool": {"error": "缺少中心地点（center），无法查询附近地点"}}

        location = _resolve_address_to_location(center_keyword, city, amap_env)
        if not location:
            return {"tool": {"error": "中心地点解析失败，无法查询附近地点"}}

        tool_args: Dict[str, Any] = {
            "keywords": around_keyword,
            "location": location,
            "radius": radius,
        }
        if city:
            tool_args["city"] = city

        tool_response = _run_async(
            _call_mcp_tool_by_spec(
                command=AMAP_MCP_COMMAND or None,
                args=AMAP_MCP_ARGS,
                env=amap_env,
                function_name=AMAP_MCP_AROUND_TOOL,
                tool_args=tool_args,
            )
        )
        return {"tool": tool_response}

    if function_name == "Search_POI_Detail":
        poi_id = str(slots.get("id", "")).strip()
        if not poi_id:
            poi_id = str(slots.get("poi_id", "")).strip()
        if not poi_id:
            keyword = str(slots.get("keywords", "")).strip() or str(slots.get("POI", "")).strip()
            city = str(slots.get("city", "")).strip()
            if keyword:
                search_args: Dict[str, Any] = {"keywords": keyword}
                if city:
                    search_args["city"] = city
                search_result = _run_async(
                    _call_mcp_tool_by_spec(
                        command=AMAP_MCP_COMMAND or None,
                        args=AMAP_MCP_ARGS,
                        env=amap_env,
                        function_name=AMAP_MCP_POI_TOOL,
                        tool_args=search_args,
                    )
                )
                poi_id = _extract_poi_id_from_text_search_result(search_result)
        if not poi_id:
            return {"tool": {"error": "缺少可识别的地点信息（id 或关键词），无法查询详情"}}

        tool_response = _run_async(
            _call_mcp_tool_by_spec(
                command=AMAP_MCP_COMMAND or None,
                args=AMAP_MCP_ARGS,
                env=amap_env,
                function_name=AMAP_MCP_SEARCH_DETAIL_TOOL,
                tool_args={"id": poi_id},
            )
        )
        return {"tool": tool_response}

    if function_name == "Route_Driving":
        origin = str(slots.get("origin", "")).strip()
        destination = str(slots.get("destination", "")).strip()
        city = str(slots.get("city", "")).strip()
        cityd = str(slots.get("cityd", "")).strip()
        strategy = str(slots.get("strategy", "")).strip()

        if not destination:
            return {"tool": {"error": "缺少终点，无法规划驾车路径"}}

        if origin:
            origin_loc = origin if "," in origin else _resolve_address_to_location(origin, city, amap_env)
            if not origin_loc:
                return {"tool": {"error": "起点地址解析失败，无法规划驾车路径"}}
        else:
            origin_loc = ""

        destination_loc = (
            destination if "," in destination else _resolve_address_to_location(destination, cityd or city, amap_env)
        )
        if not destination_loc:
            return {"tool": {"error": "终点地址解析失败，无法规划驾车路径"}}

        tool_args: Dict[str, Any] = {"destination": destination_loc}
        if origin_loc:
            tool_args["origin"] = origin_loc
        if strategy:
            tool_args["strategy"] = strategy

        tool_response = _run_async(
            _call_mcp_tool_by_spec(
                command=AMAP_MCP_COMMAND or None,
                args=AMAP_MCP_ARGS,
                env=amap_env,
                function_name=AMAP_MCP_DRIVING_TOOL,
                tool_args=tool_args,
            )
        )
        return {"tool": tool_response}

    if function_name == "Route_Transit_Integrated":
        origin = str(slots.get("origin", "")).strip()
        destination = str(slots.get("destination", "")).strip()
        city = str(slots.get("city", "")).strip()
        cityd = str(slots.get("cityd", "")).strip()

        if not destination:
            return {"tool": {"error": "缺少终点，无法规划公交路径"}}

        tool_args: Dict[str, Any] = {"destination": destination}
        if origin:
            tool_args["origin"] = origin
        if city:
            tool_args["city"] = city
        if cityd:
            tool_args["cityd"] = cityd

        tool_response = _run_async(
            _call_mcp_tool_by_spec(
                command=AMAP_MCP_COMMAND or None,
                args=AMAP_MCP_ARGS,
                env=amap_env,
                function_name=AMAP_MCP_TRANSIT_TOOL,
                tool_args=tool_args,
            )
        )
        return {"tool": tool_response}

    return None
