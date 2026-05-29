import os
import json
import re
from langchain_core.documents import Document
from kb.offline.config.env_loader import load_project_env
from main.utils.llm_client import get_llm_client


load_project_env()

LLM_CHAT_PROMPT = """
### 信息
{context}

### 任务
你是特斯拉Model 3的用户手册问答系统。请只根据上面"信息"中的内容回答问题"{query}"，禁止使用你自己的知识。
严格按照以下格式输出：

答案。【页码1, 页码2, ...】

例如：
- 请按方向盘左侧的调节杆来调整高度。【12】
- 可以通过中控屏幕设置定时充电。【25, 26】

要求：
1. 【忠实原文】只根据提供的信息回答，严禁添加信息中没有的内容。
2. 【句子整理】如果原文缺少标点断句、句式过长难以阅读，可以主动加标点、拆分长句，但不得改变原意。
3. 【页码标注】每条信息开头的【X】即为该内容对应的页码。根据实际参考内容填写对应页码。
4. 【无答案处理】如果信息中找不到答案，只说"无答案"三个字，不要解释，不要编造。
"""


def request_chat(query, context, stream=False, timeout=60.0):

    prompt = LLM_CHAT_PROMPT.format(context=context, query=query)

    llm_client = get_llm_client()
    completion = llm_client.chat.completions.create(
        model=os.getenv("DEFAULT_CHAT_MODEL", ""),
        messages=[
            {"role": "system", "content": "你只能根据参考资料回答问题，严格禁止添加自己的知识。如果参考资料不足以回答，只回答'无答案'。"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1024,
        frequency_penalty=0.3,
        temperature=0.001,
        top_p=0.1,
        stream=stream,
        extra_body={
            "top_k": 1,
            "chat_template_kwargs": {"enable_thinking": False}
        },
        timeout=timeout,
    )
    if not stream:
        result = completion.choices[0].message.content
    else:
        result = completion

    return result
