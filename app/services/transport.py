"""城际交通与住宿查询服务。

## 数据边界（重要）

本系统**没有**接入 12306 / 航司 / 酒店集团的实时库存接口，原因是：
- 12306 没有开放的下单 API，非官方协议有法律风险且频繁封号
- OTA 库存需要分销联盟资质（企业主体 + 对公账户）

因此这里做的是**可核验的推算 + 官方入口引导**：
1. **车次与票价**：基于两城真实经纬度算直线距离，按铁路实际运行经验推导
   车型（高铁/动车/普速/飞机）、大致时长与票价区间。这是估算值，会明确标注。
2. **住宿**：基于景点库的真实类型分布推荐住宿区域（住哪儿最方便），
   并给出该区域真实存在的商圈/景点锚点，价格区间按档位推算并标注为估算。
3. 两者都附官方/OTA 深链，让用户点进去看到实时余票和真实房价。

任何情况下都不编造"车次号"或"具体酒店名+房价"当真实数据卖。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.services import poi as poi_svc
from app.services.budget import distance_km

# 官方与 OTA 深链
LINKS = {
    "12306": "https://www.12306.cn/index/",
    "12306_query": "https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc&fs={f}&ts={t}&date={d}&flag=N,N,Y",
    "ctrip_train": "https://you.ctrip.com/train/",
    "qunar_train": "https://train.qunar.com/",
    "ctrip_hotel": "https://you.ctrip.com/searchsite/?keyword={kw}",
    "tongcheng_hotel": "https://www.ly.com/hotel/hotelsearch?keyword={kw}",
    "ctrip_flight": "https://you.ctrip.com/sight/airfly/search/?departcity={f}&arrivalcity={t}",
}


def _train_levels(d: float) -> list[dict[str, Any]]:
    """按直线距离推算可选的铁路/航空档次。

    数值来自国内干线的实际运行经验区间：
    速度取高铁 250-300 km/h（含停站），动车 200-250，飞机含往返机场时间约 4.5h。

    铁路营业里程约为直线距离的 1.15~1.3 倍（绕行 + 线路曲率），
    这里用 1.22 作为换算系数，这样 324km 的贵阳→重庆算出来约 395km 铁路里程，
    落在"动车 300~400km"档，而不是误判成高铁长途。
    """
    rail_km = d * 1.22
    rows: list[dict[str, Any]] = []
    # --- 铁路 ---
    if rail_km < 150:
        rows.append({"mode": "普速火车", "duration": f"{rail_km / 60:.1f}~{rail_km / 55 + 1:.1f} 小时",
                     "price": "30~80 元", "note": "多为绿皮车，班次密集，早晚车更多",
                     "kind": "train"})
    if 120 <= rail_km < 500:
        rows.append({"mode": "动车组", "duration": f"{rail_km / 180:.1f}~{rail_km / 140:.1f} 小时",
                     "price": f"{int(rail_km * 0.42)}~{int(rail_km * 0.58)} 元",
                     "note": "二等座为主，约 1 小时一班", "kind": "train"})
    if rail_km >= 500:
        rows.append({"mode": "高铁二等座", "duration": f"{rail_km / 250:.1f}~{rail_km / 200:.1f} 小时",
                     "price": f"{int(rail_km * 0.48)}~{int(rail_km * 0.66)} 元",
                     "note": "最快选择，日均多班", "kind": "train"})
        rows.append({"mode": "高铁一等座", "duration": f"{rail_km / 250:.1f}~{rail_km / 200:.1f} 小时",
                     "price": f"{int(rail_km * 0.78)}~{int(rail_km * 1.05)} 元",
                     "note": "座位宽敞，适合长途", "kind": "train"})
    # --- 航空 ---
    # 只有直线距离够远（>800km，实际航路更长）才建议飞机；
    # 800km 以下高铁几乎总是更快更省心，不推荐飞机。
    if d >= 800:
        if d < 2000:
            rows.append({"mode": "飞机（经济舱）", "duration": "1.5~2.5 小时飞行",
                         "price": f"{int(320 + d * 0.42)}~{int(620 + d * 0.75)} 元",
                         "note": "含往返机场与安检约 4~5 小时，需比高铁早 2 小时到机场",
                         "kind": "flight"})
        else:
            rows.append({"mode": "飞机（经济舱）", "duration": "2.5~3.5 小时飞行",
                         "price": f"{int(700 + d * 0.35)}~{int(1200 + d * 0.6)} 元",
                         "note": "远距离飞行优势明显", "kind": "flight"})
    if not rows:
        rows.append({"mode": "长途客车", "duration": f"{rail_km / 60:.1f}~{rail_km / 50:.1f} 小时",
                     "price": f"{int(rail_km * 0.16)}~{int(rail_km * 0.26)} 元",
                     "note": "该区间铁路直达班次较少，可考虑客运", "kind": "bus"})
    return rows


def query_trains(origin: str, dest: str, travel_date: str = "",
                 people: int = 1) -> dict[str, Any]:
    """查询两城之间的城际交通方案（估算）。

    返回时明确标注为「基于距离推算的参考区间」，并给出 12306 与 OTA 深链。
    """
    a, b = poi_svc.find_city(origin or ""), poi_svc.find_city(dest or "")
    if not a or not b:
        return {"ok": False,
                "message": f"城市未收录：{'、'.join(x for x in [origin, dest] if x and not poi_svc.find_city(x))}"}
    if a["id"] == b["id"]:
        return {"ok": False, "message": f"{a['name']}到{a['name']}是同城，无需城际交通"}

    d = distance_km(a["lat"], a["lon"], b["lat"], b["lon"])
    d_date = travel_date or (date.today() + timedelta(days=1)).isoformat()
    try:
        datetime.strptime(d_date, "%Y-%m-%d")
    except ValueError:
        d_date = (date.today() + timedelta(days=1)).isoformat()

    levels = _train_levels(d)
    train_opts = [o for o in levels if o.get("kind") == "train"]
    train_min = min((_price_num(o["price"]) for o in train_opts), default=None)

    return {
        "ok": True,
        "origin": a["name"], "dest": b["name"],
        "travel_date": d_date,
        "distance_km": d,
        "people": people,
        "options": levels,
        "recommended": levels[0]["mode"] if levels else "",
        "train_min_price": train_min,
        "links": {
            "12306": LINKS["12306"],
            "12306_query": LINKS["12306_query"].format(
                f=a["name"], t=b["name"], d=d_date),
            "ctrip": LINKS["ctrip_train"],
            "qunar": LINKS["qunar_train"],
        },
        "data_note": "时长与票价为按两城直线距离推算的参考区间，非实时余票。"
                     "真实车次、票价与余票请点下方 12306 或 OTA 链接查询。",
        "disclaimer": "本系统未接入 12306 官方接口（无开放下单 API），不做实时库存查询。",
    }


def _price_num(price: str) -> int:
    """从「120~300 元」里取下限数字。"""
    import re
    m = re.search(r"(\d+)", price.replace(",", ""))
    return int(m.group(1)) if m else 0


# ------------------------------------------------------------------ 住宿
# 住宿区域类型 → 推荐理由与真实存在的锚点类型
AREA_PROFILES = {
    "景区核心": {"desc": "出门即景点，早晚都省时间", "anchor": "景区步行 10 分钟内"},
    "交通枢纽": {"desc": "下车即入住，适合赶早班车或当日往返", "anchor": "高铁站/机场周边"},
    "市中心": {"desc": "餐饮购物方便，晚间活动多", "anchor": "商圈与商业步行街"},
    "滨江/湖畔": {"desc": "景观好、夜景佳，适合慢节奏", "anchor": "滨水步道与观景带"},
    "老城": {"desc": "有生活气，老字号小吃集中", "anchor": "老街与历史街区"},
    "近郊": {"desc": "价格通常更划算，适合自驾或包车", "anchor": "郊区与近郊景区"},
}


def _pick_areas(city_id: str) -> list[dict[str, Any]]:
    """按景点库的真实类型分布，推荐该城适合住的区域类型。"""
    pois = poi_svc.get_pois(city_id)
    if not pois:
        return []
    by_type: dict[str, list[dict[str, Any]]] = {}
    for p in pois:
        by_type.setdefault(p["type"], []).append(p)
    by_type["古镇"].sort(key=lambda p: p["heat"], reverse=True)

    # 面积分 → 住宿区域类型
    scores: dict[str, float] = {}
    for t, items in by_type.items():
        w = sum(i["heat"] for i in items) / 10.0
        if t in ("古镇", "自然", "人文"):
            scores["景区核心"] = scores.get("景区核心", 0) + w
        elif t == "美食":
            scores["市中心"] = scores.get("市中心", 0) + w * 0.8
        elif t == "城市":
            scores["市中心"] = scores.get("市中心", 0) + w
        elif t == "夜游":
            scores["市中心"] = scores.get("市中心", 0) + w * 0.9
        elif t == "体验":
            scores["近郊"] = scores.get("近郊", 0) + w

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out = []
    for area, score in ordered[:4]:
        prof = AREA_PROFILES.get(area, {"desc": "按行程动线选址", "anchor": "主要景点周边"})
        # 该区域的锚点：取该类型里最热的几个真实景点名
        anchor_types = {"景区核心": ["古镇", "自然", "人文"], "市中心": ["美食", "城市", "夜游"],
                        "交通枢纽": [], "近郊": ["体验"], "滨江/湖畔": ["自然"],
                        "老城": ["古镇", "美食"]}.get(area, [])
        anchors = []
        for t in anchor_types:
            for p in sorted(by_type.get(t, []), key=lambda x: x["heat"], reverse=True)[:2]:
                if p["name"] not in anchors:
                    anchors.append(p["name"])
        out.append({
            "area": area, "score": round(score, 1),
            "desc": prof["desc"], "anchor_type": prof["anchor"],
            "nearby": anchors[:3],
        })
    return out


def query_hotels(city: str, near_poi: str = "", people: int = 2,
                 nights: int = 2, level: str = "中等") -> dict[str, Any]:
    """推荐该城适合住的区域与住宿价位区间。

    只推荐**区域与价位区间**（基于真实景点分布推算），不编造具体酒店名与房价；
    附 OTA 深链让用户查真实房源与实时价格。
    """
    c = poi_svc.find_city(city or "")
    if not c:
        return {"ok": False, "message": f"未收录城市：{city}"}

    areas = _pick_areas(c["id"])
    if near_poi:
        hit = next((p for p in poi_svc.get_pois(c["id"]) if near_poi in p["name"]), None)
        if hit:
            # 指定了景点，把它的类型对应的区域排到最前
            prefer = {"古镇": "景区核心", "自然": "景区核心", "人文": "景区核心",
                      "美食": "市中心", "城市": "市中心", "夜游": "市中心",
                      "主题": "景区核心", "体验": "近郊", "市井": "老城",
                      "文创": "市中心"}.get(hit["type"], "")
            if prefer:
                areas.sort(key=lambda a: 0 if a["area"] == prefer else 1)
            areas[0]["nearby"] = [hit["name"]] + [x for x in areas[0]["nearby"] if x != hit["name"]]
            areas[0]["anchor_type"] = f"紧邻 {hit['name']}"

    price_band = {"经济": "120~260 元/间夜", "中等": "220~450 元/间夜",
                  "舒适": "400~800 元/间夜", "豪华": "700 元以上/间夜"}.get(level, "220~450 元/间夜")
    rooms = (people + 1) // 2
    return {
        "ok": True,
        "city": c["name"],
        "near_poi": near_poi or "",
        "people": people, "nights": nights,
        "rooms_needed": rooms,
        "price_band": price_band,
        "budget_estimate": {
            "per_room_per_night": price_band,
            "total": f"{rooms} 间 × {nights} 晚",
            "note": "按当前价位档位推算，实际房价随节假日浮动",
        },
        "areas": areas,
        "links": {
            "ctrip": LINKS["ctrip_hotel"].format(kw=c["name"]),
            "tongcheng": LINKS["tongcheng_hotel"].format(kw=c["name"]),
        },
        "data_note": "系统按景点库的真实分布推荐住宿区域与价位区间，"
                     "不含实时房价；具体酒店与当日价格请点下方 OTA 链接查看。",
        "disclaimer": "未接入酒店集团或 OTA 库存接口，不提供具体酒店报价。",
    }
