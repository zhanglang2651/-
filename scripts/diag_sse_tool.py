"""诊断：/api/chat 的 SSE 是否推了 tool 事件的 result。"""
from __future__ import annotations

import asyncio
import io
import json

import httpx

OUT = io.open("D:/shot_tmp/sse_tool.txt", "w", encoding="utf-8", buffering=1")
BASE = "http://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(timeout=180) as c:
        # 登录
        r = await c.post(f"{BASE}/api/auth/login",
                         json={"email": "lisi2026@163.com", "password": "Test123456"})
        token = r.json().get("token")
        print(f"login: {r.status_code}", file=OUT)

        payload = {"messages": [{"role": "user", "content": "查一下明天贵阳到重庆的车票"}]}
        async with c.stream("POST", f"{BASE}/api/chat", json=payload,
                            headers={"Authorization": f"Bearer {token}"}) as resp:
            ev = None
            async for line in resp.aiter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:") and ev:
                    raw = line[5:].strip()
                    try:
                        d = json.loads(raw)
                    except Exception:
                        continue
                    if ev == "tool":
                        has = "result" in d
                        print(f"TOOL event: name={d.get('name')} status={d.get('status')} "
                              f"has_result={has}", file=OUT)
                        if has:
                            print(f"   result keys: {list(d['result'].keys()) if isinstance(d['result'], dict) else type(d['result'])}", file=OUT)
                    elif ev == "error":
                        print(f"ERROR: {d}", file=OUT)
                    ev = None


asyncio.run(main())
OUT.close()
