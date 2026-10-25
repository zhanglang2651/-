"""时令模块接口验证。"""
from __future__ import annotations

import asyncio
import io
import json
import sys

import httpx

BASE = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8000}"
OUT = io.open(r"D:\文旅助手\_season_test.txt", "w", encoding="utf-8", buffering=1)


def log(*a):
    print(*a, file=OUT)


async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(f"{BASE}/api/season")
        d = r.json()

        t = d["term"]
        log("=== 当前节气 ===")
        log(f"  {t['name']} ({t['date']})  季节={t['season']}")
        log(f"  物候: {t['pheno']}")
        log(f"  气候: {t['climate']}")
        log(f"  建议: {t['advice']}")
        log(f"  下个节气: {t['next']} ({t['next_date']}) 还有 {t['days_to_next']} 天")
        log(f"  年度节气表: {len(t['year_terms'])} 条")

        log(f"\n=== 应季城市 ({len(d['best_cities'])}) ===")
        for c2 in d["best_cities"]:
            log(f"  {c2['city']} ({c2['province']}) {c2['best_season']}"
                f"  节庆={c2['festival'] or '-'}  {c2['signature']}")

        log(f"\n=== 本月节庆 ({len(d['festivals'])}) ===")
        for f in d["festivals"]:
            log(f"  {f['city']} · {f['name']}")

        log(f"\n=== 玩法主题 ({len(d['themes'])}) ===")
        for th in d["themes"]:
            log(f"  {th['icon']} {th['name']}: {th['total_cities']} 城 / {th['total_pois']} 景点")
            for cc in th["cities"][:3]:
                log(f"      - {cc['city']} · {cc['top']} ({cc['count']} 个相关景点)")

        log(f"\n=== 一城一味 ({len(d['foods'])}) ===")
        for f in d["foods"][:5]:
            dishes = "、".join(x["name"] for x in f["dishes"])
            log(f"  {f['city']}: 风味={'/'.join(f['foods'][:3])} 招牌={dishes}")

        log(f"\n=== 经典路线 ({len(d['routes'])}) ===")
        for r2 in d["routes"]:
            log(f"  【{r2['theme']}】{r2['name']} {r2['days']}天 {r2['budget']}"
                f"  {r2['season_hint']}")
            log(f"      {r2['start']} → {r2['end']} | {'、'.join(r2['tags'])}")

        log(f"\n=== 月历矩阵: {len(d['matrix']['cities'])} 城, 当前月={d['matrix']['current_month']} ===")
        for row in d["matrix"]["cities"][:5]:
            log(f"  {row['city']}: {row['best_season']} -> 月份 {row['months']}")


asyncio.run(main())
OUT.close()
