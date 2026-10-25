"""账号体系端到端测试：发码 → 注册 → 登录 → 会话 → 收藏行程。"""
from __future__ import annotations

import asyncio
import io
import json
import random
import sys

import httpx

BASE = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8000}"
OUT = io.open(r"D:\文旅助手\_auth_test.txt", "w", encoding="utf-8", buffering=1)


def log(*a):
    print(*a, file=OUT)


async def main():
    email = f"test{random.randint(10000, 99999)}@163.com"
    pwd = "Test123456"
    async with httpx.AsyncClient(timeout=60) as c:
        cfg = (await c.get(f"{BASE}/api/public-config")).json()
        log("public-config:", json.dumps(cfg, ensure_ascii=False))

        # 1. 非 163 邮箱应被拒
        bad = await c.post(f"{BASE}/api/auth/code", json={"email": "a@gmail.com"})
        log("\n[拒绝非 163] ", bad.status_code, bad.json())

        # 2. 发码
        r = await c.post(f"{BASE}/api/auth/code", json={"email": email})
        d = r.json()
        log("\n[发码]", r.status_code, json.dumps(d, ensure_ascii=False))
        code = d.get("code")
        if not code:
            log("!! 没有拿到验证码，后续跳过（可能已配置真实 SMTP）")
            OUT.close()
            return

        # 3. 弱密码应被拒
        w = await c.post(f"{BASE}/api/auth/register",
                         json={"email": email, "password": "123", "code": code,
                               "city_id": "guiyang", "nickname": "测试"})
        log("\n[弱密码]", w.status_code, w.json())

        # 4. 错误验证码
        bad2 = await c.post(f"{BASE}/api/auth/register",
                            json={"email": email, "password": pwd, "code": "000000",
                                  "city_id": "guiyang"})
        log("[错误验证码]", bad2.status_code, bad2.json())

        # 5. 正常注册
        reg = await c.post(f"{BASE}/api/auth/register",
                           json={"email": email, "password": pwd, "code": code,
                                 "city_id": "guiyang", "nickname": "浪哥"})
        log("\n[注册]", reg.status_code, json.dumps(reg.json(), ensure_ascii=False))
        if reg.status_code != 200:
            OUT.close()
            return
        token = reg.json()["token"]
        H = {"Authorization": f"Bearer {token}"}

        # 6. me
        me = (await c.get(f"{BASE}/api/auth/me", headers=H)).json()
        log("[me]", json.dumps(me, ensure_ascii=False))

        # 7. 重复注册
        dup = await c.post(f"{BASE}/api/auth/register",
                           json={"email": email, "password": pwd, "code": code, "city_id": "guiyang"})
        log("[重复注册]", dup.status_code, dup.json())

        # 8. 登录
        lg = await c.post(f"{BASE}/api/auth/login", json={"email": email, "password": pwd})
        log("\n[登录]", lg.status_code, "token_len=", len(lg.json().get("token", "")))
        lg2 = await c.post(f"{BASE}/api/auth/login", json={"email": email, "password": "wrong123"})
        log("[错误密码]", lg2.status_code, lg2.json())

        # 9. 未登录取行程收藏
        no = await c.get(f"{BASE}/api/plans")
        log("\n[未登录取行程]", no.status_code, no.json())

        # 10. 收藏行程
        sp = await c.post(f"{BASE}/api/plans", headers=H,
                          json={"payload": {"ok": True, "plan": {"city": "贵阳", "days": 3,
                                                                 "theme": "测试行程", "summary": "摘要"}}})
        log("[收藏行程]", sp.status_code, sp.json())
        pid = sp.json().get("id")

        lst = (await c.get(f"{BASE}/api/plans", headers=H)).json()
        log("[行程列表]", json.dumps(lst, ensure_ascii=False))
        one = (await c.get(f"{BASE}/api/plans/{pid}", headers=H)).json()
        log("[行程详情]", str(one)[:160])
        de = (await c.delete(f"{BASE}/api/plans/{pid}", headers=H)).json()
        log("[删除行程]", de)

        # 11. 未登录不能调规划接口
        p = await c.post(f"{BASE}/api/plan", json={"query": "贵阳2天"})
        log("\n[未登录规划]", p.status_code, (await p.aread())[:120])

        # 12. 定位
        g = (await c.get(f"{BASE}/api/geo/nearest?lat=26.58&lon=106.71")).json()
        log("\n[最近城市]", json.dumps(g, ensure_ascii=False)[:200])

        # 13. 图片
        ph = (await c.get(f"{BASE}/api/photos/guiyang")).json()
        log("[图片]", json.dumps(ph, ensure_ascii=False)[:200])

    OUT.close()


if __name__ == "__main__":
    asyncio.run(main())
