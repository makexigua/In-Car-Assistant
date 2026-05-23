"""
兼容层：历史代码仍可能 import `llm_local_client`。
当前实现已统一走 API，因此直接复用 llm_api_client。
"""

from kb.online.src.client.llm_api_client import *  # noqa: F401,F403
