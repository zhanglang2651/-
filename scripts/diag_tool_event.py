"""诊断：on_tool_end 事件的 output 到底是什么类型。"""
from __future__ import annotations

import asyncio
import io
import sys

sys.path.insert(0, r"D:\文旅助手")

from app.agents.chat_agent import get_chat_agent  # noqa: E402

OUT = io.open(r"D:\shot_tmp\tool_event.txt", "w", encoding="utf-8", buffering=1)


async def main():
    agent = get_chat_agent()
    msgs = [{"role": "user", "content": "查一下明天贵阳到重庆的车票"}]
    async for ev in agent.astream_events({"messages": msgs}, version="v2"):
        kind = ev.get("event")
        if kind == "on_tool_end":
            data = ev.get("data", {})
            out = data.get("output")
            print(f"tool={ev.get('name')}", file=OUT)
            print(f"  data keys: {list(data.keys())}", file=OUT)
            print(f"  output type: {type(out).__name__}", file=OUT)
            print(f"  output repr: {str(out)[:300]}", file=OUT)
            if hasattr(out, "content"):
                print(f"  .content type: {type(out.content).__name__}", file=OUT)
                print(f"  .content repr: {str(out.content)[:300]}", file=OUT)
            print(f"  data.output repr: {str(data.get('output'))[:200]}", file=OUT)
            print(f"  data.result repr: {str(data.get('result'))[:200]}", file=OUT)
            print("", file=OUT)


asyncio.run(main())
OUT.close()
