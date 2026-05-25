# 作用：集中维护 task 链路的路径、模型配置和默认参数，避免散落在多个文件里。

import os
from pathlib import Path
from typing import List

from main.utils.env_loader import load_project_env


load_project_env()

TASK_DIR = Path(__file__).resolve().parent
CLASS_FILE = TASK_DIR / "config" / "class.txt"
SLOT_INTENT_FILE = TASK_DIR / "config" / "slot_intent.json"


def _parse_csv_env(raw_value: str) -> List[str]:
    """把逗号分隔的环境变量转成列表，自动去掉空白项。"""
    return [item.strip() for item in (raw_value or "").split(",") if item.strip()]

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
FUNCTION_CALL_MODEL = os.getenv("FUNCTION_CALL_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))
NLG_MODEL = os.getenv("NLG_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))
REQUEST_TIMEOUT = float(os.getenv("TASK_LLM_TIMEOUT", "60"))
RECALL_TOP_K = int(os.getenv("TASK_RECALL_TOP_K", "5"))
DEFAULT_NLG = os.getenv("DEFAULT_NLG", "抱歉，这个问题我还在学习中")


AMAP_MCP_COMMAND = os.getenv("AMAP_MCP_COMMAND", "")
AMAP_MCP_ARGS = _parse_csv_env(os.getenv("AMAP_MCP_ARGS", ""))
AMAP_MAPS_API_KEY = os.getenv("AMAP_MAPS_API_KEY", "")

AMAP_MCP_WEATHER_TOOL = os.getenv("AMAP_MCP_WEATHER_TOOL", "maps_weather")
AMAP_MCP_POI_TOOL = os.getenv("AMAP_MCP_POI_TOOL", "maps_text_search")
AMAP_MCP_SEARCH_DETAIL_TOOL = os.getenv("AMAP_MCP_SEARCH_DETAIL_TOOL", "maps_search_detail")
AMAP_MCP_TRANSIT_TOOL = os.getenv("AMAP_MCP_TRANSIT_TOOL", "maps_direction_transit_integrated")
AMAP_MCP_AROUND_TOOL = os.getenv("AMAP_MCP_AROUND_TOOL", "maps_around_search")
AMAP_MCP_DRIVING_TOOL = os.getenv("AMAP_MCP_DRIVING_TOOL", "maps_direction_driving")
