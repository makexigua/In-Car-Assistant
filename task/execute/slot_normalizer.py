# 作用：兼容旧 task 链路的槽位名映射和值归一化逻辑。

import json
import re
from typing import Any, Dict, Optional

from task.settings import SLOT_INTENT_FILE


SLOT_MAP = json.loads(SLOT_INTENT_FILE.read_text(encoding="utf-8"))

POSITION_MAP = {
    "主驾": "MAIN",
    "副驾": "VICE",
    "左侧": "LEFT",
    "右侧": "RIGHT",
    "前排": "FRONT",
    "后排": "REAR",
    "左后": "LEFT_REAR",
    "右后": "RIGHT_REAR",
    "主对角": "MAIN_DIAGONAL",
    "副对角": "VICE_DIAGONAL",
    "所有": "ALL",
    "吹脚": "FOOT",
    "吹脸": "FACE",
    "吹窗": "WINDOW",
    "吹脸吹脚": "FACE_AND_FOOT",
    "吹窗吹脚": "WINDOW_AND_FOOT",
    "左前": "MAIN",
    "右前": "VICE",
    "主副驾": "FRONT",
}


def _safe_to_float(raw_value: str) -> Optional[float]:
    value = (raw_value or "").strip()
    if not value:
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return float(value)
    if re.fullmatch(r"-?\d+(\.\d+)?/-?\d+(\.\d+)?", value):
        left, right = value.split("/", 1)
        denominator = float(right)
        if denominator == 0:
            return None
        return float(left) / denominator
    return None


def normalize_slot_value(slot_key: str, slot_value: Any) -> Any:
    if slot_value is None:
        return slot_value

    value = str(slot_value).strip()
    if not value:
        return value

    key_lower = slot_key.lower()
    if key_lower in {"number", "ratio"}:
        if "%" in value:
            number = _safe_to_float(value.replace("%", ""))
            return number / 100 if number is not None else value
        number = _safe_to_float(value)
        return number if number is not None else value

    if slot_key in {"POSITION", "位置"}:
        return POSITION_MAP.get(value, value)

    if slot_key == "对话时长":
        return value.replace("秒", "")

    if slot_key == "Extreme":
        if value in {"最大", "最高", "最强", "最亮", "最热"}:
            return "最大"
        if value in {"最小", "最低", "最弱", "最暗", "最冷"}:
            return "最小"

    return value


def normalize_slots(function_name: str, raw_slots: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_slots, dict):
        return {}

    slot_rules = SLOT_MAP.get(function_name)
    normalized: Dict[str, Any] = {}
    for raw_key, raw_value in raw_slots.items():
        if raw_value in (None, "", "不限"):
            continue

        mapped_key = raw_key
        if isinstance(slot_rules, dict):
            mapped_key = slot_rules.get(raw_key, raw_key)

        normalized[mapped_key] = normalize_slot_value(mapped_key, raw_value)
    return normalized
