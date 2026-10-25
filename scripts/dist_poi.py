"""分析 POI 类型/标签分布，用于校准玩法主题匹配规则。"""
from __future__ import annotations

import io
import sys
from collections import Counter

sys.path.insert(0, r"D:\文旅助手")
from app.services import poi as poi_svc  # noqa: E402

OUT = io.open(r"D:\shot_tmp\poi_dist.txt", "w", encoding="utf-8", buffering=1)

types = Counter()
tags = Counter()
per_city_food = {}
for c in poi_svc.list_cities():
    pois = poi_svc.get_pois(c["id"])
    for p in pois:
        types[p["type"]] += 1
        for t in p.get("tags", []):
            tags[t] += 1
    food = [p["name"] for p in pois if p["type"] == "美食"]
    per_city_food[c["name"]] = food

print("=== 类型分布 ===", file=OUT)
for t, n in types.most_common():
    print(f"  {t}: {n}", file=OUT)

print("\n=== 标签 TOP 60 ===", file=OUT)
for t, n in tags.most_common(60):
    print(f"  {t}: {n}", file=OUT)

print("\n=== 各城美食型 POI ===", file=OUT)
for city, foods in per_city_food.items():
    print(f"  {city}: {foods}", file=OUT)
OUT.close()
