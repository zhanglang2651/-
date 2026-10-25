"""端到端自检脚本：逐个打接口，把结果落到文本文件。"""
from __future__ import annotations

import asyncio
import io
import json
import sys

import httpx

BASE = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8000}"
OUT = io.open(r"D:\文旅助手\_selftest.txt", "w", encoding="utf-8", buffering=1)


def log(*args):
    print(*args, file=OUT)
    OUT.flush()


async def main():
    async with httpx.AsyncClient(timeout=180) as c:
        # 1. health
        h = (await c.get(f"{BASE}/api/health")).json()
        log("== HEALTH ==", json.dumps(h, ensure_ascii=False))

        # 2. trends
        t = (await c.get(f"{BASE}/api/trends/guiyang")).json()
        log("\n== TRENDS guiyang ==")
        log("weather:", t["weather"]["source"], t["weather"]["current"])
        log("calendar:", t["calendar"])
        log("briefing:", json.dumps(t["briefing"], ensure_ascii=False))
        for it in t["items"][:5]:
            log(f'  #{it["rank"]} {it["name"]} heat={it["heat_now"]} delta={it["delta"]} '
                f'level={it["level"]} crowd={it["crowd_text"]} | {it["reason"]}')
        log("advice:", t["items"][0]["advice"])

        # 3. overview
        o = (await c.get(f"{BASE}/api/trends/overview?limit=6")).json()
        log("\n== OVERVIEW ==")
        for r in o["items"]:
            log(f'  {r["city"]}: {r["hot_name"]} {r["heat"]:.0f} {r["level"]} '
                f'{r["weather"].get("text")} {r["weather"].get("temp")}℃')

        # 4. plan (SSE)
        log("\n== PLAN (SSE) ==")
        steps, plan = [], None
        async with c.stream("POST", f"{BASE}/api/plan",
                            json={"query": "贵阳玩3天，带爸妈，节奏轻松，想吃酸汤鱼，预算中等"}) as r:
            ev, data = None, []
            async for line in r.aiter_lines():
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    data.append(line[5:].strip())
                elif line == "":
                    if ev and data:
                        payload = json.loads("".join(data))
                        if ev == "step":
                            steps.append(f'{payload.get("key")}/{payload.get("status")}: '
                                         f'{payload.get("detail")}')
                        elif ev == "plan":
                            plan = payload
                        elif ev == "error":
                            log("  ERROR EVENT:", payload)
                        elif ev == "done":
                            log("  done:", payload)
                    ev, data = None, []
        log("  steps:")
        for s in steps:
            log("   ", s)

        if plan:
            p = plan.get("plan", {})
            log("  ok:", plan.get("ok"), "| errors:", plan.get("errors"))
            log("  city:", p.get("city"), "| days:", p.get("days"), "| theme:", p.get("theme"))
            log("  summary:", p.get("summary"))
            log("  budget:", json.dumps(p.get("budget"), ensure_ascii=False))
            for d in p.get("itinerary", []):
                log(f'  --- Day {d.get("day")} {d.get("date")} {d.get("title")} '
                    f'[{d.get("weather", {}).get("text")} {d.get("weather", {}).get("rain_prob")}%]')
                for it in d.get("items", []):
                    log(f'      {it.get("time")} {it.get("name")} ({it.get("type")}, '
                        f'{it.get("hours")}h, ¥{it.get("cost")}) - {it.get("desc")}')
                for m in d.get("meals", []):
                    log(f'      餐 {m.get("time")} {m.get("name")} @{m.get("place")} ¥{m.get("cost")}')
            log("  tips:", p.get("tips"))
        else:
            log("  !! 未收到 plan 事件")

    OUT.close()


if __name__ == "__main__":
    asyncio.run(main())
