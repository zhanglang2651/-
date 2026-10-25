"""统计景点图片覆盖情况。"""
from __future__ import annotations

import io
import sys

sys.path.insert(0, r"D:\文旅助手")

from app.services import poi as poi_svc  # noqa: E402
from app.services import poi_photos as pps  # noqa: E402

OUT = io.open("D:/shot_tmp/coverage.txt", "w", encoding="utf-8")

total = withimg = 0
for c in poi_svc.list_cities():
    pois = poi_svc.get_pois(c["id"])
    m = pps.load_manifest(c["id"])
    got = [p["name"] for p in pois if m.get(p["name"])]
    total += len(pois)
    withimg += len(got)
    if got:
        print(f"{c['name']}: {len(got)}/{len(pois)}", file=OUT)

print(f"\n总计 {withimg}/{total} 个景点有图 ({withimg/total*100:.0f}%)", file=OUT)
print(f"图片文件数: {pps.poi_photo_stats()['photos']}", file=OUT)
OUT.close()
