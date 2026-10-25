"""限流感知的景点图片补齐器。

Unsplash 免费档每小时 50 次搜索请求，全量 240 个景点一次跑不完。
这个脚本会：
1. 只处理「还没有图」的景点
2. 遇到限流就等待冷却时间再继续（而不是直接放弃）
3. 断点续跑 —— 下次启动时自动跳过已有图的景点
"""
from __future__ import annotations

import asyncio
import io
import sys
import time

sys.path.insert(0, r"D:\文旅助手")

from app.services import poi as poi_svc  # noqa: E402
from app.services import poi_photos as svc  # noqa: E402

OUT = io.open("D:/shot_tmp/fetch_loop.txt", "w", encoding="utf-8")
DELAY = 1.3        # 秒/次，正常限流内
COOLDOWN = 600     # 限流后等待秒数（Unsplash 按小时重置）


def log(*a):
    print(*a, file=OUT)
    OUT.flush()


async def main():
    max_rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    cities = poi_svc.list_cities()

    for rnd in range(1, max_rounds + 1):
        pending = []
        for c in cities:
            m = svc.load_manifest(c["id"])
            for p in poi_svc.get_pois(c["id"]):
                if not m.get(p["name"]):
                    pending.append((c["id"], c["name"], p["name"]))
        if not pending:
            log(f"[轮次 {rnd}] 全部景点都有图了")
            break

        log(f"\n[轮次 {rnd}] 待处理 {len(pending)} 个景点")
        done = limited = 0
        for cid, cname, pname in pending:
            try:
                items = await svc.fetch_poi_photos(cid, pname)
            except Exception as e:  # noqa: BLE001
                log(f"  ! {cname}/{pname}: {str(e)[:60]}")
                items = []
            if items:
                done += 1
                log(f"  ✓ {cname}/{pname}: {len(items)} 张")
            else:
                limited += 1
                rl = svc.rate_limit_state()
                if rl["limited"]:
                    log(f"  ⏸ 触发限流，等待 {COOLDOWN}s 后继续（剩余 {len(pending) - done - limited}）")
                    await asyncio.sleep(COOLDOWN)
                    break
            await asyncio.sleep(DELAY)

        rl = svc.rate_limit_state()
        total_photos = svc.poi_photo_stats()["photos"]
        log(f"  本轮新增 {done} 张，累计 {total_photos} 张"
            f"{'（限流冷却中）' if rl['limited'] else ''}")
        if rl["limited"] and rnd < max_rounds:
            await asyncio.sleep(COOLDOWN)

    st = svc.poi_photo_stats()
    log(f"\n结束：{st['photos']} 张图，覆盖 {st['cities']} 城")
    OUT.close()


asyncio.run(main())
