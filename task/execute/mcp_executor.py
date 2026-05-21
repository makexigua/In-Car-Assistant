# 作用：执行地图、天气、音乐等需要走 MCP 的任务型能力。

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from sinan import Sinan

from main.utils import logger
from task.mcp_core.mcp_client import MCPClient
from task.settings import AMP_SERVER_PATH, MUSIC_SERVER_PATH


MCP_FUNCTIONS = {
    "Query_Weather",
    "Query_Timely_Weather",
    "Go_POI",
    "Search_Music",
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


async def _call_mcp_tool(server_path: str, function_name: str, tool_args: Dict[str, Any]) -> Any:
    client = MCPClient()
    try:
        await client.connect_to_server(server_path)
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


def execute_mcp_function(function_name: str, slots: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if function_name in {"Query_Weather", "Query_Timely_Weather"}:
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
            _call_mcp_tool(
                server_path=AMP_SERVER_PATH,
                function_name="maps_weather",
                tool_args={"city": city, "date": date},
            )
        )
        return {"executor": "mcp", "tool": tool_response}

    if function_name == "Go_POI":
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
            _call_mcp_tool(
                server_path=AMP_SERVER_PATH,
                function_name="maps_text_search",
                tool_args=tool_args,
            )
        )
        return {"executor": "mcp", "tool": tool_response}

    if function_name == "Search_Music":
        keyword = " ".join([str(value) for value in slots.values() if str(value).strip()]).strip()
        if not keyword:
            keyword = "流行"

        tool_response = _run_async(
            _call_mcp_tool(
                server_path=MUSIC_SERVER_PATH,
                function_name="search_music",
                tool_args={"keyword": keyword, "page": 1, "num": 3},
            )
        )
        return {"executor": "mcp", "tool": tool_response}

    return None
