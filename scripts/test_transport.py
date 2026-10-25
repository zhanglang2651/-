"""交通与住宿服务验证。"""
from __future__ import annotations

import io
import json
import sys

sys.path.insert(0, r"D:\文旅助手")

from app.services.transport import query_hotels, query_trains  # noqa: E402

OUT = io.open(r"D:\文旅助手\_transport_test.txt", "w", encoding="utf-8", buffering=1)


def log(*a):
    print(*a, file=OUT)


log("=== 车票：明天 贵阳 → 重庆 ===")
r = query_trains("贵阳", "重庆")
log(f"  距离 {r['distance_km']} km  日期 {r['travel_date']}")
for o in r["options"]:
    log(f"  · {o['mode']}: {o['duration']}  {o['price']}")
    log(f"      {o['note']}")
log(f"  12306深链: {r['links']['12306_query']}")
log(f"  说明: {r['data_note']}")

log("\n=== 车票：上海 → 杭州 ===")
r2 = query_trains("上海", "杭州")
for o in r2["options"]:
    log(f"  · {o['mode']}: {o['duration']}  {o['price']}")

log("\n=== 车票：北京 → 拉萨（远途） ===")
r3 = query_trains("北京", "拉萨")
log(f"  距离 {r3['distance_km']} km")
for o in r3["options"]:
    log(f"  · {o['mode']}: {o['duration']}  {o['price']}")

log("\n=== 异常：同城 ===")
log(f"  {query_trains('贵阳', '贵阳')}")

log("\n=== 异常：未收录城市 ===")
log(f"  {query_trains('贵阳', '火星')}")

log("\n=== 酒店：贵阳 · 近天河潭 ===")
h = query_hotels("贵阳", near_poi="天河潭", people=2, nights=2, level="舒适")
log(f"  价位 {h['price_band']}  需 {h['rooms_needed']} 间 × {h['nights']} 晚")
for a in h["areas"]:
    log(f"  · {a['area']}（{a['score']}）: {a['desc']}")
    log(f"      锚点: {a['anchor_type']} | {a['nearby']}")

log("\n=== 酒店：重庆（不指定景点） ===")
h2 = query_hotels("重庆", people=2, nights=3, level="经济")
for a in h2["areas"]:
    log(f"  · {a['area']}: {a['desc']} | {a['nearby']}")

log("\n=== 酒店：苏州 · 近拙政园 ===")
h3 = query_hotels("苏州", near_poi="拙政园")
log(f"  首选区域: {h3['areas'][0]['area']} — {h3['areas'][0]['anchor_type']}")

log("\n=== 数据边界声明 ===")
log(f"  {h['data_note']}")
log(f"  {h['disclaimer']}")
OUT.close()
