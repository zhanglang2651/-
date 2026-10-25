"""预算与距离估算。

城际交通不再用固定数字，而是按「出发地 → 目的地」的直线距离分档估算往返成本。
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.services import poi as poi_svc

LEVEL_PRICE = {
    "经济": {"stay": 180, "meal": 80, "local": 30},
    "中等": {"stay": 380, "meal": 150, "local": 50},
    "舒适": {"stay": 700, "meal": 280, "local": 80},
    "豪华": {"stay": 1300, "meal": 500, "local": 120},
}


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * r * asin(sqrt(a)), 1)


def intercity(origin: str, dest: str, people: int = 2) -> dict[str, Any]:
    """按距离分档估算往返城际交通。"""
    a, b = poi_svc.find_city(origin or ""), poi_svc.find_city(dest or "")
    if not a or not b:
        per = 800
        return {"cost": per * people, "per_person": per, "distance_km": None,
                "note": "未识别出发地，按人均 800 元往返估算；填写出发地可精确到距离分档"}
    if a["id"] == b["id"]:
        return {"cost": 0, "per_person": 0, "distance_km": 0,
                "note": f"{a['name']}同城出行，无城际交通"}
    d = distance_km(a["lat"], a["lon"], b["lat"], b["lon"])
    if d < 150:
        per, mode = 120, "高铁/大巴"
    elif d < 400:
        per, mode = 260, "高铁"
    elif d < 800:
        per, mode = 450, "高铁"
    elif d < 1500:
        per, mode = 780, "高铁/机票"
    else:
        per, mode = 1200, "机票"
    return {"cost": per * people, "per_person": per, "distance_km": d, "mode": mode,
            "note": f"{a['name']} → {b['name']} 直线约 {d:.0f} km，按{mode}往返人均 {per} 元估算"}


def estimate(days: int, people: int = 2, level: str = "中等",
             origin: str = "", dest: str = "", tickets: int = 0) -> dict[str, Any]:
    p = LEVEL_PRICE.get(level, LEVEL_PRICE["中等"])
    rooms = (people + 1) // 2
    stay = p["stay"] * rooms * max(0, days - 1)
    meal = p["meal"] * people * days
    local = p["local"] * people * days
    ic = intercity(origin, dest, people)
    breakdown = {
        "住宿": stay, "餐饮": meal, "门票": tickets,
        "市内交通": local, "城际交通": ic["cost"],
    }
    return {"breakdown": breakdown, "total": sum(breakdown.values()),
            "intercity_note": ic["note"], "distance_km": ic.get("distance_km")}
