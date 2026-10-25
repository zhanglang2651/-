"""Agent 可调用的工具集（LangChain Tool）。

这些工具同时服务于两条链路：
1. 固定编排的行程规划图（context 节点直接调用）
2. 自由问答的 ReAct Agent（由模型自主决定调用哪个）
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from app.services import budget as budget_svc
from app.services import poi as poi_svc
from app.services import transport as transport_svc
from app.services import trends as trend_svc
from app.services import weather as weather_svc


@tool
async def tool_weather(city_name: str) -> str:
    """查询某个城市未来 7 天的真实天气（气温、降水概率、天气现象）。输入城市中文名，如"贵阳"。"""
    city = poi_svc.find_city(city_name)
    if not city:
        return json.dumps({"error": f"未收录城市：{city_name}"}, ensure_ascii=False)
    w = await weather_svc.fetch_weather(city["lat"], city["lon"], 7)
    return json.dumps({
        "city": city["name"], "source": w["source"], "current": w["current"],
        "daily": [{k: d[k] for k in ("date", "text", "t_min", "t_max", "rain_prob")} for d in w["daily"]],
    }, ensure_ascii=False)


@tool
async def tool_attractions(city_name: str, preference: str = "", budget: str = "中等", limit: int = 8) -> str:
    """按偏好检索某城市的真实景点候选池（含评分、票价、建议时长、最佳时段）。
    preference 可以是"自然/亲子/美食/古镇/夜景/人文"等关键词组合。"""
    city = poi_svc.find_city(city_name)
    if not city:
        return json.dumps({"error": f"未收录城市：{city_name}"}, ensure_ascii=False)
    w = await weather_svc.fetch_weather(city["lat"], city["lon"], 3)
    daily = w["daily"][0] if w.get("daily") else {}
    pois = poi_svc.get_pois(city["id"])
    fit_map = {p["name"]: weather_svc.weather_fit(daily, p.get("indoor", False))[0] for p in pois}
    picked = poi_svc.recommend(city["id"], preference, fit_map, budget, limit)
    return json.dumps([{k: p[k] for k in ("name", "type", "rating", "hours", "ticket",
                                          "best", "desc", "tags", "indoor")}
                       | {"weather_fit": p["weather_fit"]} for p in picked], ensure_ascii=False)


@tool
async def tool_hot_ranking(city_name: str) -> str:
    """查询某城市当下的旅游热点热度榜（实时计算的热度指数、拥挤度、涨跌、错峰建议）。"""
    city = poi_svc.find_city(city_name)
    if not city:
        return json.dumps({"error": f"未收录城市：{city_name}"}, ensure_ascii=False)
    data = await trend_svc.city_trends(city["id"], with_ai=False)
    return json.dumps({
        "city": data["city"]["name"],
        "calendar": data["calendar"]["label"],
        "weather": data["weather"]["current"],
        "top": [{k: i[k] for k in ("rank", "name", "heat_now", "delta", "level", "crowd_text", "advice")}
                for i in data["items"][:6]],
    }, ensure_ascii=False)


@tool
async def tool_poi_detail(name: str) -> str:
    """按名称精确查询某个景点的详情：票价、建议时长、评分、最佳时段、所属城市、实时热度。
    用户问「XX 多少钱 / 几点去 / 在哪」时优先用这个工具。"""
    hits = poi_svc.search(name, limit=3)
    if not hits:
        return json.dumps({"query": name, "found": False,
                           "message": f"知识库中没有「{name}」这个景点，可以改用城市名查询该城热门景点，或建议用户核实名称。"},
                          ensure_ascii=False)
    return json.dumps({"query": name, "found": True, "matches": [
        {k: h.get(k) for k in ("name", "city", "type", "rating", "hours",
                               "ticket", "best", "desc", "tags", "heat")}
        for h in hits]}, ensure_ascii=False)


@tool
def tool_budget(days: int, people: int = 2, level: str = "中等",
                origin: str = "", destination: str = "") -> str:
    """按天数/人数/消费档位估算旅行预算。origin 是出发城市，destination 是目的地城市，
    提供后城际交通会按实际距离分档估算；不提供则按人均 800 元兜底。"""
    est = budget_svc.estimate(days=days, people=people, level=level,
                              origin=origin, dest=destination)
    return json.dumps({
        "days": days, "people": people, "level": level,
        "breakdown": est["breakdown"], "total": est["total"],
        "intercity_note": est["intercity_note"],
        "note": "门票按实际选择的景点累加，此处未含",
    }, ensure_ascii=False)


@tool
def tool_city_list() -> str:
    """列出系统收录的全部城市及其特色标签。"""
    return json.dumps([{"name": c["name"], "province": c["province"], "tags": c["tags"],
                        "best_season": c["best_season"]} for c in poi_svc.list_cities()],
                      ensure_ascii=False)


@tool
def tool_train_query(origin: str, destination: str, travel_date: str = "",
                     people: int = 1) -> str:
    """查询两个城市之间的城际交通方案（高铁/动车/飞机），含大致时长、票价区间与购票链接。

    用于回答「明天贵阳到重庆的车票」「上海到杭州怎么走」「坐高铁要多久多少钱」这类问题。
    travel_date 格式 YYYY-MM-DD，留空默认明天。返回的是按距离推算的参考区间，
    并附 12306 与 OTA 链接供查询真实余票。
    """
    r = transport_svc.query_trains(origin, destination, travel_date, people)
    return json.dumps(r, ensure_ascii=False)


@tool
def tool_hotel_recommend(city: str, near_poi: str = "", people: int = 2,
                          nights: int = 2, level: str = "中等") -> str:
    """推荐某个城市适合住宿的区域、价位区间与预订入口。

    用于回答「住哪儿方便」「附近有什么酒店」「住一晚多少钱」「亲子住哪个区域」这类问题。
    near_poi 可指定想住的景点附近（如"西江千户苗寨""外滩"），系统会据此调整推荐顺序。
    返回的是基于景点分布推算的区域建议与价位区间，并附 OTA 链接查真实房源。
    """
    r = transport_svc.query_hotels(city, near_poi, people, nights, level)
    return json.dumps(r, ensure_ascii=False)


PLAN_TOOLS = [tool_weather, tool_attractions, tool_hot_ranking, tool_budget]
CHAT_TOOLS = [tool_poi_detail, tool_weather, tool_attractions,
              tool_hot_ranking, tool_budget, tool_city_list,
              tool_train_query, tool_hotel_recommend]
