"""批量预热景点图片（Unsplash 拉取并落地缓存）。

用法：
  python scripts/fetch_poi_photos.py            # 全部城市
  python scripts/fetch_poi_photos.py guiyang    # 指定城市
  python scripts/fetch_poi_photos.py guiyang 青岩古镇  # 指定景点

注意：Unsplash 免费档每小时 50 次搜索请求，脚本已内置节流与断点续跑。
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
import time

sys.path.insert(0, r"D:\文旅助手")

from app.services import poi as poi_svc  # noqa: E402
from app.services import poi_photos as svc  # noqa: E402

OUT = io.open(r"D:\文旅助手\_poi_photos_report.txt", "w", encoding="utf-8", buffering=1)
DELAY = 1.4   # 秒/次，控制在 Unsplash 限流内


async def main():
    args = sys.argv[1:]
    if args:
        cities = [poi_svc.get_city(a) for a in args if poi_svc.get_city(a)]
        wanted = {a for a in args if not poi_svc.get_city(a)}
    else:
        cities = poi_svc.list_cities()
        wanted = set()

    total_poi = ok_poi = 0
    total_img = 0
    for c in cities:
        names = [p["name"] for p in poi_svc.get_pois(c["id"])]
        if wanted:
            names = [n for n in names if n in wanted]
        if not names:
            continue
        got = 0
        for n in names:
            total_poi += 1
            existing = svc.public_poi_photos(c["id"], n)
            if existing:
                ok_poi += 1
                got += len(existing)
                total_img += len(existing)
                continue
            try:
                items = await svc.fetch_poi_photos(c["id"], n)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {c['name']}/{n}: {str(e)[:60]}", file=OUT)
                items = []
            if items:
                ok_poi += 1
                got += len(items)
                total_img += len(items)
                print(f"  ✓ {c['name']}/{n}: {len(items)} 张", file=OUT)
            else:
                print(f"  · {c['name']}/{n}: 无结果", file=OUT)
            await asyncio.sleep(DELAY)
        print(f"[{c['name']}] 完成 {got} 张", file=OUT)

    print(f"\n共 {total_poi} 个景点，成功 {ok_poi} 个，累计 {total_img} 张图", file=OUT)
    OUT.close()


asyncio.run(main())
