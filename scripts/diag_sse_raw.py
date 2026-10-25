import asyncio
import io
import httpx

OUT = io.open("D:/shot_tmp/sse_raw.txt", "w", encoding="utf-8")
BASE = "http://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(BASE + "/api/auth/login",
                         json={"email": "lisi2026@163.com", "password": "Test123456"})
        token = r.json().get("token")
        payload = {"messages": [{"role": "user", "content": "查一下明天贵阳到重庆的车票"}]}
        headers = {"Authorization": "Bearer " + token}
        raw = b""
        async with c.stream("POST", BASE + "/api/chat", json=payload, headers=headers) as resp:
            async for chunk in resp.aiter_bytes():
                raw += chunk
                if b"tool" in raw and b'"done"' in raw and len(raw) > 3000:
                    # 找到含 result 的那块
                    if b'"result"' in raw:
                        break
        print("total bytes:", len(raw), file=OUT)
        # 找 tool done 块
        idx = raw.find(b'"result"')
        if idx > 0:
            start = raw.rfind(b"event: tool", 0, idx)
            if start < 0:
                start = max(0, idx - 300)
            seg = raw[start:idx + 200]
            print("--- raw segment ---", file=OUT)
            print(repr(seg[:700]), file=OUT)
        # 分隔符检测
        print("has \\n\\n:", raw.count(b"\n\n"), file=OUT)
        print("has \\r\\n\\r\\n:", raw.count(b"\r\n\r\n"), file=OUT)
        print("has \\n\\r\\n:", raw.count(b"\n\r\n"), file=OUT)
    OUT.close()


asyncio.run(main())
