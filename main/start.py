import json
import os
import time
import traceback
import copy
import base64
import queue
import threading
import warnings
from typing import Any, Dict
from pathlib import Path

from flask import Flask, Response, request, jsonify, make_response, stream_with_context, send_from_directory

# 抑制第三方库的过期警告（如 jieba 的 pkg_resources）
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

# 抑制第三方库的过期警告（如 jieba 的 pkg_resources）
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

# 请求取消共享状态（trace_id → bool）
_cancelled: Dict[str, bool] = {}
_cancel_lock = threading.Lock()


def _is_cancelled(trace_id: str) -> bool:
    with _cancel_lock:
        return _cancelled.get(trace_id, False)


def _mark_cancelled(trace_id: str):
    with _cancel_lock:
        _cancelled[trace_id] = True

from main.client.arbitration import request_arbitration
from main.client.task import request_task
from main.client.rag import request_rag
from main.client.reject import is_reject_passed, request_reject
from main.client.rewrite import request_rewrite
from main.client.chat import request_chat, process_chat
from main.utils import logger
from main.utils.env_loader import load_project_env
from main.utils.session_memory import add_user_query, complete_answer, get_session_turns


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


load_project_env()
DEFAULT_NLG = os.getenv("DEFAULT_NLG", "抱歉，这个问题我还在学习中")
ENABLE_DEBUG_API = os.getenv("ENABLE_DEBUG_API", "false").strip().lower() in ("1", "true", "yes", "y")

# 后台预热 MCP 连接，避免第一个请求等 npx 启动
from task.execute.mcp_executor import init_mcp as _warmup_mcp

def _mcp_warmup():
    ok = _warmup_mcp()
    if ok:
        logger.info("[启动预热] MCP 初始化成功，工具已就绪")
    else:
        logger.warning("[启动预热] MCP 初始化失败（后续请求会重试）")

threading.Thread(target=_mcp_warmup, daemon=True, name="mcp-warmup").start()

# 图片静态目录
BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_DIR = str(BASE_DIR / "kb" / "offline" / "data" / "processed" / "images")


# 图片静态路由
@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)


INTENT_META = {
    "REJECT": ("拒识", "400"),
    "TASK": ("任务执行", "401"),
    "RAG": ("知识库问答", "402"),
    "CHAT": ("闲聊百科", "403"),
    "PROCESSING": ("处理中", "500"),
}


@app.route("/health", methods=["GET"])
def check():
    return make_response(jsonify(health="healthy"), 200)


@app.route("/cancel/<trace_id>", methods=["POST"])
def cancel(trace_id):
    _mark_cancelled(trace_id)
    logger.info(f"Request cancelled by user, trace_id={trace_id}")
    return make_response(jsonify(cancelled=True), 200)


@app.route("/debug/session/<sender_id>", methods=["GET"])
def debug_session(sender_id: str):
    if not ENABLE_DEBUG_API:
        return make_response(jsonify(error="debug api disabled"), 403)

    include_pending_raw = request.args.get("include_pending", "true")
    include_pending = str(include_pending_raw).strip().lower() in ("1", "true", "yes", "y")

    limit_raw = request.args.get("limit", "3")
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 3
    limit = max(1, min(limit, 20))

    turns = get_session_turns(
        sender_id=sender_id,
        limit=limit,
        include_pending=include_pending,
    )
    return make_response(jsonify({
        "sender_id": sender_id,
        "include_pending": include_pending,
        "limit": limit,
        "count": len(turns),
        "turns": turns,
    }), 200)


def _encode_frame(response_payload, route, frame, seq, cost, status) -> str:
    """把参数拼成一帧 JSON（替换原先 socketio 的 send_msg）。"""
    route = (route or "").upper()
    intent, intent_id = INTENT_META.get(route, INTENT_META["REJECT"])

    if route != "TASK" or not response_payload.get("intent"):
        response_payload["intent"] = intent
        response_payload["intent_id"] = intent_id
    elif not response_payload.get("intent_id"):
        response_payload["intent_id"] = intent_id
    response_payload["route"] = route.lower()
    response_payload["frame"] = frame
    response_payload["seq"] = seq
    response_payload["cost"] = cost
    response_payload["status"] = status
    return json.dumps(response_payload, ensure_ascii=False) + "\n"


def _build_template(query, trace_id, begin) -> Dict[str, Any]:
    return {
        "query": query,
        "trace_id": trace_id,
        "intent": "",
        "intent_id": "",
        "function": "",
        "slots": {},
        "route": "",
        "cost": time.time() - begin,
    }


def _with_heartbeat(fn, template, begin, trace_id="", heartbeat_interval=5):
    """
    在线程中执行阻塞函数 fn，等待期间每 heartbeat_interval 秒 yield 一个心跳帧，
    以保持 TCP 连接活跃，防止浏览器/代理超时断开。
    如果 trace_id 被取消或前端断开连接，会抛出 InterruptedError。

    使用方式（yield from 可以捕获 return 值）：

        result = yield from _with_heartbeat(lambda: request_task(...), template, begin)

    如果 fn 抛出异常，会透传到外层。
    """
    result_q = queue.Queue()

    def _worker():
        try:
            result = fn()
            result_q.put(("ok", result))
        except BaseException as e:
            result_q.put(("error", e))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    last_heartbeat = time.time()
    while True:
        try:
            kind, val = result_q.get(timeout=1)
            if kind == "ok":
                return val
            else:
                raise val
        except queue.Empty:
            # 优先检测中断：前端断开 或 用户手动取消
            if request.is_disconnected():
                raise InterruptedError(f"Client disconnected, trace_id={trace_id}")
            if trace_id and _is_cancelled(trace_id):
                raise InterruptedError(f"Request cancelled by user, trace_id={trace_id}")
            # 每 heartbeat_interval 秒发一次心跳帧
            if time.time() - last_heartbeat >= heartbeat_interval:
                last_heartbeat = time.time()
                yield _encode_frame(copy.deepcopy(template), "PROCESSING", "", 0, time.time() - begin, status=3)


@app.route("/agent", methods=["POST"])
def inference():
    begin = time.time()
    req_data = request.get_json(force=True)
    query = req_data.get("query", "").strip()
    enable_dm = req_data.get("enable_dm", True)
    sender_id = req_data.get("sender_id", "test")
    trace_id = req_data.get("trace_id", "123")

    def _stream():
        nonlocal query
        template = _build_template(query, trace_id, begin)

        # 立即发开始帧，让前端知道连接正常，避免代理超时断开
        yield _encode_frame(template, "START", "", 0, 0, status=0)

        try:
            ori_query = query
            logger.session.trace_id = trace_id
            logger.info("Request Params: {}".format(req_data))

            # 1) 拒识（用心跳保护，防止 LLM 响应慢导致连接断开）
            reject_result = yield from _with_heartbeat(
                lambda: request_reject(ori_query, trace_id), template, begin, trace_id=trace_id
            )
            if _is_cancelled(trace_id):
                logger.info(f"Request cancelled after reject, trace_id={trace_id}")
                return
            if not is_reject_passed(reject_result):
                yield _encode_frame(template, "REJECT", "", 1, time.time() - begin, status=-1)
                logger.info(f"Query {ori_query} rejected by reject model.")
                return

            # 2) 写入短期记忆
            add_user_query(sender_id, ori_query, trace_id)

            # 3) 改写（用心跳保护）
            query = yield from _with_heartbeat(
                lambda: request_rewrite(ori_query, sender_id, trace_id), template, begin, trace_id=trace_id
            )
            if _is_cancelled(trace_id):
                logger.info(f"Request cancelled after rewrite, trace_id={trace_id}")
                return

            # 4) 仲裁（用心跳保护），返回 (route, function_scope)
            arbitration_result, function_scope = yield from _with_heartbeat(
                lambda: request_arbitration(query, sender_id, trace_id), template, begin, trace_id=trace_id
            )
            if _is_cancelled(trace_id):
                logger.info(f"Request cancelled after arbitration, trace_id={trace_id}")
                return
            logger.info(f"TraceID:{trace_id}, query:{query}, route:{arbitration_result}, scope:{function_scope}")

            # 5) 任务链路（可能耗时较长，用心跳包装防止连接断开）
            if arbitration_result == "task":
                response_payload = yield from _with_heartbeat(
                    lambda: request_task(query, trace_id, enable_dm, function_scope=function_scope),
                    template, begin, trace_id=trace_id
                )
                if _is_cancelled(trace_id):
                    logger.info(f"Request cancelled during task pipeline, trace_id={trace_id}")
                    return
                nlg_content = response_payload.get("nlg", "")
                has_function = response_payload.get("function", "Unknown") not in ["Unknown", ""]
                if nlg_content or has_function:
                    answer = nlg_content or DEFAULT_NLG
                    complete_answer(sender_id=sender_id, trace_id=trace_id, route="task",
                                    answer=answer, query_fallback=ori_query)
                    yield _encode_frame(response_payload, "TASK", answer, 1, time.time() - begin, status=2)
                else:
                    yield _encode_frame(response_payload, "REJECT", DEFAULT_NLG, 1, time.time() - begin, status=-1)
                    complete_answer(sender_id=sender_id, trace_id=trace_id, route="task",
                                    answer=DEFAULT_NLG, query_fallback=ori_query)

            # 6) RAG 链路（也可能耗时较长，用心跳包装）
            elif arbitration_result == "rag":
                # 将 request_rag 与图片 base64 编码一并放入心跳 worker，
                # 避免图片编码阻塞主生成器导致连接超时断开
                def _request_rag_with_images():
                    _result = request_rag(query, trace_id, sender_id)
                    _images = _result.get("related_images", [])
                    for _img in _images:
                        _img_path = _img.get("image_path", "")
                        if _img_path and os.path.exists(_img_path):
                            with open(_img_path, "rb") as _f:
                                _img_data = _f.read()
                            _ext = os.path.splitext(_img_path)[1].lstrip(".") or "png"
                            _b64 = base64.b64encode(_img_data).decode()
                            _img["url"] = f"data:image/{_ext};base64,{_b64}"
                    _result["related_images"] = _images
                    return _result

                rag_result = yield from _with_heartbeat(
                    _request_rag_with_images, template, begin, trace_id=trace_id
                )
                if _is_cancelled(trace_id):
                    logger.info(f"Request cancelled during rag pipeline, trace_id={trace_id}")
                    return
                answer = rag_result.get("answer", "")
                if answer:
                    rag_payload = _build_template(ori_query, trace_id, begin)
                    # 图片 URL 已在 worker 线程中生成
                    rag_payload["related_images"] = rag_result.get("related_images", [])
                    rag_payload["cite_pages"] = rag_result.get("cite_pages", [])
                    rag_payload["citations"] = rag_result.get("citations", [])
                    yield _encode_frame(rag_payload, "RAG", answer, 1, time.time() - begin, status=2)
                    complete_answer(sender_id=sender_id, trace_id=trace_id, route="rag",
                                    answer=answer, query_fallback=ori_query)
                else:
                    # RAG 无答案 → 闲聊兜底
                    yield from _chat_stream(template, query, sender_id, trace_id, begin, ori_query)

            # 7) 闲聊链路（已经是流式的了，无需心跳）
            else:
                yield from _chat_stream(template, query, sender_id, trace_id, begin, ori_query)

        except InterruptedError as e:
            logger.info(f'TraceID:{trace_id}, Request cancelled: {e}')
            yield _encode_frame(template, "REJECT", "", 1, time.time() - begin, status=-1)
        except Exception as e:
            logger.error(f'TraceID:{trace_id}, Internal Server Error!')
            logger.error(f'{e}')
            traceback.print_exc()
            yield _encode_frame(template, "REJECT", "", 1, time.time() - begin, status=-1)

    return Response(stream_with_context(_stream()), mimetype="text/plain")


def _chat_stream(template, query, sender_id, trace_id, begin, ori_query):
    """闲聊链路流式生成器，逐帧 yield（带心跳保护）。"""
    seq = 1
    payload_begin = copy.deepcopy(template)
    yield _encode_frame(payload_begin, "CHAT", "", seq, time.time() - begin, status=0)

    full_answer = ""
    result_q = queue.Queue()
    chat_stop = threading.Event()

    def _worker():
        """在后台线程中执行 LLM 流式调用，逐 token 放入队列。"""
        try:
            chat_handler = request_chat(query, sender_id, trace_id)
            for value in process_chat(chat_handler, query, sender_id):
                if chat_stop.is_set():
                    return
                result_q.put(("token", value))
            result_q.put(("done", None))
        except BaseException as e:
            result_q.put(("error", e))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    is_hit = False
    while True:
        if _is_cancelled(trace_id):
            chat_stop.set()
            logger.info(f"Chat stream cancelled by user, trace_id={trace_id}")
            break
        try:
            kind, val = result_q.get(timeout=5)
            if kind == "token":
                is_hit = True
                seq += 1
                payload = copy.deepcopy(template)
                yield _encode_frame(payload, "CHAT", val, seq, time.time() - begin, status=1)
                full_answer += val
            elif kind == "done":
                break
            elif kind == "error":
                raise val
        except queue.Empty:
            # 心跳帧：LLM 仍在生成（首 token 延迟或 token 间间隙过长）
            yield _encode_frame(copy.deepcopy(template), "PROCESSING", "", 0, time.time() - begin, status=3)

    if is_hit:
        yield _encode_frame(payload_begin, "CHAT", "", seq, time.time() - begin, status=2)
        complete_answer(sender_id=sender_id, trace_id=trace_id, route="chat",
                        answer=full_answer, query_fallback=ori_query)
        logger.info(f"Chat cost time: {time.time() - begin}")


if __name__ == "__main__":
    app.run(
        host='0.0.0.0',
        debug=True,
        port=os.getenv("FLASK_SERVER_PORT", 8080),
        threaded=True,
    )