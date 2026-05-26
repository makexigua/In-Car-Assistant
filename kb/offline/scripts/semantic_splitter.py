import os
import re
import json
from openai import OpenAI

from kb.offline.config.env_loader import load_project_env

load_project_env()

llm_client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", ""),
    base_url=os.getenv("LLM_BASE_URL", ""),
)

LLM_SPLIT_PROMPT = """你是一个文档处理助手。请将以下文本按语义主题切分成若干段落。

要求：
1. 每个段落围绕一个独立主题
2. 段落之间不要重复内容
3. 段落数量控制在 {target_chunks} 个左右
4. 输出格式必须是 JSON，格式如下：{{"chunks": ["段落1内容", "段落2内容", ...]}}
5. 不要添加任何解释，只输出 JSON

文本内容：
{text}

请输出 JSON："""

_MIN_DOC_SIZE = 256
_MIN_CHUNK_SIZE = 50


def semantic_split(text: str, group_size: int = 10) -> list[str]:
    """语义切分主函数。

    策略：
    1. 短文本直接返回
    2. 按 ### 标题切分
    3. 按 \n\n 切分
    4. 长文本调用 LLM API 做语义切分
    """
    if len(text) <= _MIN_DOC_SIZE:
        return [text]

    chunks = _split_by_headers(text)
    if len(chunks) > 1:
        return chunks

    chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
    if len(chunks) <= group_size:
        return chunks

    target_chunks = max(2, len(chunks) // group_size + 1)
    return _llm_split(text, target_chunks)


def _split_by_headers(text: str) -> list[str]:
    """按 ### 标题切分。"""
    parts = re.split(r"(###)", text)
    parts = [k for k in parts if k.strip()]
    if not parts:
        return []
    if parts[0] == "###":
        chunks = ["".join(parts[i : i + 2]) for i in range(0, len(parts), 2)]
    else:
        chunks = [parts[0]] + ["".join(parts[i : i + 2]) for i in range(1, len(parts), 2)]
    return [c.strip() for c in chunks if c.strip()]


def _llm_split(text: str, target_chunks: int) -> list[str]:
    """调用 LLM API 做语义切分，失败时回退到按空行切分。"""
    prompt = LLM_SPLIT_PROMPT.format(text=text, target_chunks=target_chunks)
    try:
        completion = llm_client.chat.completions.create(
            model=os.getenv("DEFAULT_CHAT_MODEL", ""),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.001,
            top_p=0,
        )
        result = completion.choices[0].message.content
        chunks = _parse_json_chunks(result)
        if chunks:
            return chunks
    except Exception as e:
        print(f"LLM semantic split failed: {e}")

    return [c.strip() for c in text.split("\n\n") if c.strip()]


def _parse_json_chunks(text: str) -> list[str] | None:
    """从 LLM 输出中解析 JSON chunks。"""
    try:
        data = json.loads(text)
        if "chunks" in data and isinstance(data["chunks"], list):
            return [c.strip() for c in data["chunks"] if c.strip()]
    except json.JSONDecodeError:
        pass

    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(text[start : end + 1])
            if "chunks" in data and isinstance(data["chunks"], list):
                return [c.strip() for c in data["chunks"] if c.strip()]
    except (json.JSONDecodeError, ValueError):
        pass

    return None
