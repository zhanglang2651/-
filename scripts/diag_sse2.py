import asyncio
import io
import json
import httpx

OUT = io.open("D:/shot_tmp/sse_tool.txt", "w", encoding="utf-8")
BASE = "http://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(BASE + "/api/auth/login",
                         json={"email": "lisi2026@163.com", "password": "Test123456"})
        token = r.json().get("token")
        print("login:", r.status_code, file=OUT)
        payload = {"messages": [{"role": "user", "content": "查一下明天贵阳到重庆的车票"}]}
        headers = {"Authorization": "Bearer " + token}
        async with c.stream("POST", BASE + "/api/chat", json=payload, headers=headers) as resp:
            ev = None
            async for line in resp.aiter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:") and ev:
                    try:
                        d = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    if ev == "tool":
                        res = d.get("result")
                        print("TOOL", d.get("name"), d.get("status"),
                              "has_result=", "result" in d,
                              "type=", type(res).__name__, file=OUT)
                        if isinstance(res, dict):
                            print("   keys=", list(res.keys()), file=OUT)
                    elif ev == "error":
                        print("ERROR", d, file=OUT)
                    ev = None
    OUT.close()


asyncio.run(main())
