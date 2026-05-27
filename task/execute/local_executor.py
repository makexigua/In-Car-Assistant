# 作用：处理车载本地能力的执行描述，给后端或前端一个统一的本地动作载荷。

from typing import Any, Dict, Optional


def build_local_action(function_name: str, slots: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not function_name or function_name == "Unknown":
        return None

    return {
        "type": "local_function",
        "function": function_name,
        "arguments": slots,
    }
