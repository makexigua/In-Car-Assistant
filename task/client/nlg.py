import requests
import json
import time
import os
from typing import Any
import prompts
from utils import logger
from utils.env_loader import load_project_env


TIMEOUT = 10.0
load_project_env()
DOUBAO_API_KEY = os.getenv("LLM_API_KEY", os.getenv("API_KEY", ""))
DOUBAO_URL = os.getenv("LLM_BASE_URL", os.getenv("BASE_URL", ""))
NLG_MODEL = os.getenv("NLG_MODEL", os.getenv("DEFAULT_CHAT_MODEL", "ep-20241203180921-h2kgz"))
NLG_PROMPT = prompts.NLG_PROMPT


def request_nlg(query, tool_response):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": DOUBAO_API_KEY
        }
        messages = [
            {"role": "user", "content": NLG_PROMPT.format(query, tool_response)}
        ]

        body = dict(
            model=NLG_MODEL,
            messages=messages,
        )
        response = requests.post(
            DOUBAO_URL,
            headers=headers,
            json=body,
            timeout=TIMEOUT
        )
        response = response.json()
        answer = response["choices"][0]["message"]["content"]
        logger.info(f"NLG结果: {answer}")
        return answer

    except Exception:
        logger.error("Call NLG API failed.")
        return ""


if __name__ == "__main__":
    
    query = "今天天气怎么样"
    tool_response = "城市：北京市\n天气：阴\n温度：21度\n风向：东北\n风力：1-3级"

    res = request_nlg(query, tool_response)
    print(res)
