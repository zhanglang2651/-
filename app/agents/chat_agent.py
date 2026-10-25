"""自由问答智能体：LangGraph ReAct（工具自主调用 + 流式输出）。"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable

from app.agents.prompts import CHAT_SYSTEM
from app.agents.tools import CHAT_TOOLS
from app.core.llm import get_streaming_llm

_agent = None

# 部分模型会把工具协议标签吐进正文，这里统一清掉
_BLOCK_RE = re.compile(r"<(tool_call|tool_response|tool_result)>[\s\S]*?</\1>", re.I)
_TAG_RE = re.compile(r"</?(?:tool_call|tool_response|tool_result|function_call|im_start|im_end)[^>]*>", re.I)


def clean_model_text(text: str) -> str:
    cleaned = _BLOCK_RE.sub("", text)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"^\s*[}{]\s*", "", cleaned)
    return cleaned.strip()


def _extract_tool_payload(output: Any) -> Any:
    """从工具返回值里抽出可 JSON 化的结果。

    LangGraph 的 on_tool_end 里 output 可能是 ToolMessage 对象，
    其 .content 才是工具返回的字符串。
    """
    if output is None:
        return None
    if isinstance(output, dict):
        return output
    content = getattr(output, "content", None)
    if content is None and isinstance(output, str):
        content = output
    if isinstance(content, list):
        # 部分版本 content 是内容块列表
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "text":
                content = blk.get("text")
                break
        else:
            return None
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (ValueError, TypeError):
            return None
    return None


def get_chat_agent():
    global _agent
    if _agent is not None:
        return _agent
    llm = get_streaming_llm(0.6)
    from langgraph.prebuilt import create_react_agent

    for kwargs in ({"prompt": CHAT_SYSTEM}, {"state_modifier": CHAT_SYSTEM},
                   {"messages_modifier": CHAT_SYSTEM}, {}):
        try:
            _agent = create_react_agent(llm, CHAT_TOOLS, **kwargs)
            break
        except TypeError:
            continue
    return _agent


async def stream_chat(history: list[dict[str, str]], emit: Callable[[dict[str, Any]], None]) -> str:
    """执行对话并把 token / 工具事件通过 emit 推出，返回完整回答文本。"""
    agent = get_chat_agent()
    if agent is None:
        raise RuntimeError("对话 Agent 初始化失败，请检查依赖版本")

    msgs = [m for m in history if m.get("role") in ("user", "assistant")][-10:]
    full: list[str] = []
    try:
        async for ev in agent.astream_events({"messages": msgs}, version="v2"):
            kind = ev.get("event")
            if kind == "on_chat_model_stream":
                content = ev["data"]["chunk"].content
                if isinstance(content, str) and content:
                    full.append(content)
                    emit({"type": "token", "text": content})
            elif kind == "on_tool_start":
                emit({"type": "tool", "status": "start", "name": ev.get("name"),
                      "input": ev["data"].get("input")})
            elif kind == "on_tool_end":
                # 把工具结果也推出去，前端据此渲染车票/住宿等结构化卡片
                payload = _extract_tool_payload(ev.get("data", {}).get("output"))
                emit({"type": "tool", "status": "done", "name": ev.get("name"),
                      "result": payload})
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        emit({"type": "error", "message": f"对话失败：{exc}"})
    return clean_model_text("".join(full))
