"""检查主题区分度：各主题命中城市数是否合理。"""
from __future__ import annotations

import io
import sys

sys.path.insert(0, r"D:\文旅助手")
from app.services.seasonal import theme_overview  # noqa: E402

OUT = io.open(r"D:\shot_tmp\theme_dist.txt", "w", encoding="utf-8", buffering=1)

total_cities = 30
for t in theme_overview():
    pct = t["total_cities"] / total_cities * 100
    print(f"{t['icon']} {t['name']}: {t['total_cities']} 城 ({pct:.0f}%) / {t['total_pois']} 景点", file=OUT)
    for c in t["cities"][:4]:
        print(f"    {c['city']} score={c['score']} count={c['count']} top={c['top']}"
              f" foods={c.get('foods')}", file=OUT)
OUT.close()
