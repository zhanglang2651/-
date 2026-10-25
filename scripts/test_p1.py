"""P1 功能验证：单日重排 / 分享短链 / 邮件发送。"""
from __future__ import annotations

import asyncio
import io
import json
import os
import random
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(r"D:\文旅助手\.env", encoding="utf-8")

BASE = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8000}"
OUT = io.open(r"D:\文旅助手\_p1_test.txt", "w", encoding="utf-8", buffering=1)


def log(*a):
    print(*a, file=OUT)


async def main():
    real_mail = os.getenv("SMTP_USER", "")
    async with httpx.AsyncClient(timeout=180) as c:
        cfg = (await c.get(f"{BASE}/api/public-config")).json()
        log("mail_ready:", cfg["mail_ready"], "| photos_ready:", cfg["photos_ready"],
            "| photos:", cfg["photos"])

        # ---------- 邮件（发给配置的发件邮箱自己，验证通道） ----------
        if real_mail:
            r = (await c.post(f"{BASE}/api/auth/code", json={"email": real_mail})).json()
            log(f"\n[发码→{real_mail[:3]}***]", json.dumps(r, ensure_ascii=False))
        else:
            log("\n[发码] 未配置 SMTP_USER，跳过")

        # ---------- 用已有账号登录 ----------
        lg = await c.post(f"{BASE}/api/auth/login",
                          json={"email": "lisi2026@163.com", "password": "Test123456"})
        if lg.status_code != 200:
            log("!! 测试账号登录失败：", lg.text[:200])
            OUT.close()
            return
        token = lg.json()["token"]
        H = {"Authorization": f"Bearer {token}"}
        log("[登录] 成功", lg.json()["user"]["nickname"])

        # ---------- 单日重排 ----------
        fake_plan = {
            "city": "贵阳", "days": 2, "theme": "测试",
            "summary": "测试行程",
            "budget": {"total": 1000, "breakdown": {"住宿": 380, "餐饮": 300, "门票": 50,
                                                    "市内交通": 100, "城际交通": 170}},
            "itinerary": [
                {"day": 1, "date": "2026-10-26", "title": "室内文化",
                 "weather": {"text": "小雨", "t_min": 15, "t_max": 20, "rain_prob": 90},
                 "items": [{"time": "09:00", "name": "贵州省博物馆", "type": "人文",
                            "hours": 2.5, "cost": 0, "desc": "看展"}],
                 "meals": [], "stay": "市区", "day_cost": 200},
                {"day": 2, "date": "2026-10-27", "title": "自然",
                 "weather": {"text": "多云", "t_min": 15, "t_max": 22, "rain_prob": 20},
                 "items": [{"time": "09:00", "name": "黔灵山公园", "type": "自然",
                            "hours": 3, "cost": 5, "desc": "爬山"}],
                 "meals": [], "stay": "市区", "day_cost": 200},
            ],
        }
        log("\n[重排 Day1] 请求中…（约 20-40 秒）")
        rv = await c.post(f"{BASE}/api/plan/revise", headers=H,
                          json={"plan": fake_plan, "day": 1,
                                "instruction": "换成一个室内景点，晚上加个夜市小吃"})
        log("status:", rv.status_code)
        if rv.status_code == 200:
            new_plan = rv.json()["plan"]
            d1 = new_plan["itinerary"][0]
            log("  Day1 新标题:", d1["title"])
            log("  Day1 景点:", [i["name"] for i in d1["items"]])
            log("  Day1 餐食:", [m["name"] for m in d1["meals"]])
            log("  Day2 是否未变:", [i["name"] for i in new_plan["itinerary"][1]["items"]])
            log("  预算:", json.dumps(new_plan["budget"], ensure_ascii=False))
        else:
            log("  ", rv.text[:300])

        # ---------- 分享 ----------
        payload = {"ok": True, "plan": fake_plan, "city": {"name": "贵阳", "accent": "#4ade80"},
                   "brief": {"people": 3, "budget_level": "中等", "origin": "成都"}}
        sp = (await c.post(f"{BASE}/api/plans", headers=H, json={"payload": payload})).json()
        log("\n[收藏]", sp)
        share = (await c.post(f"{BASE}/api/plans/{sp['id']}/share", headers=H)).json()
        log("[分享]", share)

        pub = (await c.get(f"{BASE}/api/share/{share['token']}")).json()
        log("[公开读取] status ok, city=", pub["city"], "author=", pub["author"])

        # 未登录访问分享页
        page = await c.get(f"{BASE}/s/{share['token']}")
        log("[分享页]", page.status_code, "contains 行程分享:", "行程分享" in page.text)

        log("\nSHARE_TOKEN=" + share["token"])
    OUT.close()


if __name__ == "__main__":
    asyncio.run(main())
