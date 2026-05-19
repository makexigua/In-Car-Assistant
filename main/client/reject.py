# 作用：调用拒识服务，判断用户问题是否合规可继续处理。

import json
import os

import requests
from utils import logger
from utils.env_loader import load_project_env


THRESHOLD = 0.5
REQUEST_TIMEOUT = 5.0


load_project_env()
REJECT_BASE_URL = os.getenv("REJECT_BASE_URL", "")
REJECT_API_KEY = os.getenv("REJECT_API_KEY", "")
REJECT_URL = os.getenv("REJECT_URL", "")

# 返回 target_url, headers, mode
def _build_reject_target():
    if REJECT_BASE_URL and REJECT_API_KEY:
        return REJECT_BASE_URL, {
            "Content-Type": "application/json",
            "Authorization": REJECT_API_KEY,
        }, "remote"

    if REJECT_URL:
        return REJECT_URL, {"Content-Type": "application/json"}, "local"

    return "", {}, "none"


def request_reject(query, trace_id):
    target_url, headers, mode = _build_reject_target()
    if mode == "none":
        logger.error(
            "reject config missing: need (REJECT_BASE_URL + REJECT_API_KEY) or REJECT_URL, default pass."
        )
        return "是"   # 表示不拒识

    payload = json.dumps({"query": query, "thres": THRESHOLD, "trace_id": trace_id}, ensure_ascii=False)

    try:
        response = requests.post(target_url, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        text = response.json()["data"]
        logger.info(f"拒识模型的输出：{text}, mode:{mode}")
        return text
    except Exception as err:
        logger.error(f"call reject failed:{err}")
        return "是"


if __name__ == "__main__":
    while True:
        query = input("Input:")
        print(request_reject(query, "123"))
