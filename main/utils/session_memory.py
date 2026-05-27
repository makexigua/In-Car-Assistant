# 作用：维护短期会话记忆（query/answer/route/trace_id），统一供改写/仲裁/chat读取。

import json
import time
from typing import Any, Dict, List, Optional

from main.utils import logger
from main.utils.redis_tool import RedisClient


SESSION_KEY = "voice:session:{}"
MAX_TURNS = 3
TURN_EXPIRE_SECONDS = 60
_redis_client = RedisClient()


def _now_ts() -> int:
    return int(time.time())


def _normalize_turn(item: Any, now_ts: int) -> Optional[Dict[str, Any]]:
    """
    把 redis 里的单条 turn 归一化成固定字段。
    如果已过期或字段非法，返回 None。
    """
    if not isinstance(item, dict):
        return None

    query = str(item.get("query", "")).strip()
    answer = str(item.get("answer", "")).strip()
    route = str(item.get("route", "")).strip()
    trace_id = str(item.get("trace_id", "")).strip()

    created_at_raw = item.get("created_at", now_ts)
    updated_at_raw = item.get("updated_at", created_at_raw)
    expires_at_raw = item.get("expires_at", int(updated_at_raw) + TURN_EXPIRE_SECONDS)

    try:
        created_at = int(created_at_raw)
        updated_at = int(updated_at_raw)
        expires_at = int(expires_at_raw)
    except Exception:
        return None

    # 每轮单独过期：超过 60s 直接丢弃。
    if expires_at <= now_ts:
        return None

    # 没有 query 的记录没有可用语义，直接丢弃。
    if not query:
        return None

    return {
        "query": query,
        "answer": answer,
        "route": route,
        "trace_id": trace_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "expires_at": expires_at,
    }


def _read_turns(sender_id: str) -> List[Dict[str, Any]]:
    """
    读取并清洗会话 turn 列表：
    - 过滤过期轮次
    - 保留时间顺序
    """
    key = SESSION_KEY.format(sender_id)
    raw = _redis_client.get(key)
    if not raw:
        logger.info(f"redis session get empty, sender_id={sender_id}, key={key}")
        return []

    now_ts = _now_ts()
    try:
        payload = json.loads(raw)
    except Exception:
        logger.error(f"redis session json decode failed, sender_id={sender_id}, key={key}")
        return []

    turns_raw = payload.get("turns", [])
    if not isinstance(turns_raw, list):
        return []

    need_flush = False
    turns: List[Dict[str, Any]] = []
    for item in turns_raw:
        turn = _normalize_turn(item, now_ts)
        if turn is not None:
            turns.append(turn)
        else:
            need_flush = True

    turns.sort(key=lambda x: x.get("created_at", 0))
    turns = turns[-MAX_TURNS:]

    # 读阶段顺手清理 Redis：把过期轮次和超长轮次从 value 里真正删掉。
    if need_flush or len(turns_raw) > len(turns):
        _write_turns(sender_id, turns)

    logger.info(f"redis session read_turns done, sender_id={sender_id}, turns_count={len(turns)}")
    return turns


def _write_turns(sender_id: str, turns: List[Dict[str, Any]]) -> None:
    """
    写回会话 turn 列表：
    - 空列表时删除 key
    - 非空时刷新 key TTL=60s（最后一轮后 60s 自动清空）
    """
    key = SESSION_KEY.format(sender_id)
    if not turns:
        _redis_client.delete(key)
        logger.info(f"redis session delete key (empty turns), sender_id={sender_id}, key={key}")
        return

    payload = {"turns": turns[-MAX_TURNS:]}
    _redis_client.set(key, json.dumps(payload, ensure_ascii=False), ex=TURN_EXPIRE_SECONDS)
    logger.info(f"redis session write_turns done, sender_id={sender_id}, turns_count={len(turns)}")


def add_user_query(sender_id: str, query: str, trace_id: str) -> None:
    """
    拒识通过后先写入 query，占位 answer。
    """
    now_ts = _now_ts()
    turns = _read_turns(sender_id)

    # 同一个 trace_id 可能重入，这里先去重，避免重复占位。
    turns = [item for item in turns if item.get("trace_id") != trace_id]
    turns.append(
        {
            "query": (query or "").strip(),
            "answer": "",
            "route": "",
            "trace_id": (trace_id or "").strip(),
            "created_at": now_ts,
            "updated_at": now_ts,
            "expires_at": now_ts + TURN_EXPIRE_SECONDS,
        }
    )
    _write_turns(sender_id, turns)
    logger.info(f"redis session add_user_query done, sender_id={sender_id}, trace_id={trace_id}, query={query[:50]}")


def complete_answer(
    sender_id: str,
    trace_id: str,
    route: str,
    answer: str,
    query_fallback: str = "",
) -> None:
    """
    在 task/rag/chat 完成后，按 trace_id 回填 answer 与 route。
    """
    now_ts = _now_ts()
    turns = _read_turns(sender_id)
    updated = False

    # 从后往前找最近一条匹配 trace_id 的 turn，更符合真实请求顺序。
    for index in range(len(turns) - 1, -1, -1):
        if turns[index].get("trace_id") == trace_id:
            turns[index]["answer"] = (answer or "").strip()
            turns[index]["route"] = (route or "").strip()
            turns[index]["updated_at"] = now_ts
            turns[index]["expires_at"] = now_ts + TURN_EXPIRE_SECONDS
            updated = True
            break

    if not updated:
        # 兜底：如果没找到占位 query，仍补一条完整 turn，避免这轮上下文丢失。
        turns.append(
            {
                "query": (query_fallback or "").strip(),
                "answer": (answer or "").strip(),
                "route": (route or "").strip(),
                "trace_id": (trace_id or "").strip(),
                "created_at": now_ts,
                "updated_at": now_ts,
                "expires_at": now_ts + TURN_EXPIRE_SECONDS,
            }
        )

    # 再做一次清洗，保证不会把空 query 的兜底记录写回去。
    valid_turns = []
    for item in turns:
        turn = _normalize_turn(item, now_ts)
        if turn is not None:
            valid_turns.append(turn)
    _write_turns(sender_id, valid_turns)
    logger.info(f"redis session complete_answer done, sender_id={sender_id}, trace_id={trace_id}, route={route}, answer={str(answer)[:50]}")


def get_completed_turns(
    sender_id: str,
    limit: int = MAX_TURNS,
    exclude_trace_id: str = "",
) -> List[Dict[str, Any]]:
    """
    读取“有 answer 的历史轮次”。
    改写/仲裁/chat 只看这类轮次，避免读到当前轮未完成数据。
    """
    turns = _read_turns(sender_id)
    result: List[Dict[str, Any]] = []
    for item in turns:
        if exclude_trace_id and item.get("trace_id") == exclude_trace_id:
            continue
        if item.get("answer"):
            result.append(item)
    return result[-max(1, limit):]


def get_session_turns(
    sender_id: str,
    limit: int = MAX_TURNS,
    include_pending: bool = True,
) -> List[Dict[str, Any]]:
    """
    调试用途：读取会话内的短期记忆。
    include_pending=False 时，只返回 answer 已回填的轮次。
    """
    turns = _read_turns(sender_id)
    if include_pending:
        return turns[-max(1, limit):]
    return [item for item in turns if item.get("answer")][-max(1, limit):]


def build_role_history(
    sender_id: str,
    limit: int = MAX_TURNS,
    exclude_trace_id: str = "",
) -> List[Dict[str, str]]:
    """
    把会话 turn 转成 LLM messages:
    user(query) -> assistant(answer)
    """
    turns = get_completed_turns(
        sender_id=sender_id,
        limit=limit,
        exclude_trace_id=exclude_trace_id,
    )
    messages: List[Dict[str, str]] = []
    for item in turns:
        query = item.get("query", "")
        answer = item.get("answer", "")
        if query:
            messages.append({"role": "user", "content": query})
        if answer:
            messages.append({"role": "assistant", "content": answer})
    return messages
