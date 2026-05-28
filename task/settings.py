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

# 导航/距离查询的默认起点坐标，格式 "经度,纬度"
# 当用户未指定起点时自动使用此值（如 "导航去上海" → origin 用此值）
DEFAULT_ORIGIN = os.getenv("DEFAULT_ORIGIN", "")

# ----------------------------------------------------------------
# MCP 弹性配置（熔断、重试、超时）
# ----------------------------------------------------------------

MCP_CONNECT_TIMEOUT = float(os.getenv("MCP_CONNECT_TIMEOUT", "30"))
"""MCP 连接超时（秒）。"""

MCP_CALL_TIMEOUT = float(os.getenv("MCP_CALL_TIMEOUT", "30"))
"""单次 MCP 工具调用超时（秒）。"""

MCP_RETRY_MAX = int(os.getenv("MCP_RETRY_MAX", "2"))
"""MCP 调用失败最大重试次数（不含首次）。"""

MCP_CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("MCP_CIRCUIT_BREAKER_THRESHOLD", "3"))
"""熔断器触发阈值：连续失败次数。"""

MCP_RECOVERY_TIMEOUT = float(os.getenv("MCP_RECOVERY_TIMEOUT", "30"))
"""熔断器恢复超时（秒）：OPEN → HALF_OPEN 等待时间。"""
