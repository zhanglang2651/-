"""POI 知识库：城市元数据 + 景点库的加载、检索与排序。"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import settings


@lru_cache(maxsize=1)
def _load_cities() -> list[dict[str, Any]]:
    data = json.loads((settings.data_dir / "cities.json").read_text(encoding="utf-8"))
    for c in data:
        c["poi_count"] = len(get_pois(c["id"]))
    return data


@lru_cache(maxsize=1)
def _load_pois() -> dict[str, list[dict[str, Any]]]:
    return json.loads((settings.data_dir / "pois.json").read_text(encoding="utf-8"))


def list_cities() -> list[dict[str, Any]]:
    return _load_cities()


def get_pois(city_id: str) -> list[dict[str, Any]]:
    return _load_pois().get(city_id, [])


def find_city(query: str) -> dict[str, Any] | None:
    """按中文名 / 拼音 id / 别称模糊匹配城市。"""
    if not query:
        return None
    q = query.strip().lower().replace("市", "").replace(" ", "")
    cities = _load_cities()
    for c in cities:
        if q in (c["name"], c["id"], c["name"].lower()):
            return c
    for c in cities:
        if q in c["name"] or q in c["id"] or any(q in t for t in c["tags"]):
            return c
    alias = {"黔东南苗族侗族自治州": "qiandongnan", "黔东南州": "qiandongnan", "帝都": "beijing",
             "魔都": "shanghai", "春城": "kunming", "羊城": "guangzhou", "山城": "chongqing"}
    if q in alias:
        target = alias[q]
        return next((c for c in cities if c["id"] == target), None)
    return None


def get_city(city_id: str) -> dict[str, Any] | None:
    return next((c for c in _load_cities() if c["id"] == city_id), None)


TYPE_KEYS = ["自然", "人文", "古镇", "美食", "夜游", "城市", "主题", "体验", "文创", "市井"]


def classify_pref(text: str) -> dict[str, float]:
    """把用户偏好/天气/人群描述映射成类型权重，用于 POI 排序。"""
    w = {k: 0.0 for k in TYPE_KEYS}
    rules = {
        "自然": ["自然", "山", "水", "湖", "瀑", "徒步", "户外", "风景", "拍照", "梯田", "雪山"],
        "人文": ["人文", "历史", "博物", "遗址", "寺庙", "文化", "研学", "古城", "遗产"],
        "古镇": ["古镇", "古村", "苗寨", "侗寨", "村", "屯堡"],
        "美食": ["吃", "美食", "小吃", "夜市", "美食街", "火锅", "粉"],
        "夜游": ["夜", "夜景", "晚上", "酒吧", "灯光"],
        "城市": ["citywalk", "逛街", "购物", "商圈", "街拍", "咖啡"],
        "主题": ["乐园", "迪士尼", "亲子", "游乐"],
        "体验": ["体验", "骑行", "竹筏", "索道", "漂流", "演出"],
        "文创": ["文创", "艺术", "展览", "拍照点"],
        "市井": ["市井", "茶馆", "本地", "生活", "安静"],
    }
    for k, kws in rules.items():
        for kw in kws:
            if kw in text:
                w[k] += 1.0
    return w


def score_poi(poi: dict[str, Any], pref: dict[str, float], fit: int, budget_level: float) -> float:
    """综合排序分：热度基础 + 偏好匹配 + 天气适配 + 评分 + 预算敏感度。"""
    base = poi["heat"] * 0.35
    type_bonus = pref.get(poi["type"], 0.0) * 9.0
    tag_bonus = sum(pref.get(t, 0.0) for t in poi.get("tags", []) if t in pref) * 3.0
    rating = (poi["rating"] - 4.0) * 14.0
    weather_bonus = (fit - 70) * 0.35
    price_penalty = poi["ticket"] * budget_level * 0.06
    return base + type_bonus + tag_bonus + rating + weather_bonus - price_penalty


def recommend(
    city_id: str,
    pref_text: str = "",
    fit_map: dict[str, int] | None = None,
    budget: str = "中等",
    limit: int = 6,
) -> list[dict[str, Any]]:
    """按条件为某城市挑选最合适的景点。fit_map: {景点名: 天气适配分}"""
    pois = get_pois(city_id)
    pref = classify_pref(pref_text + budget)
    budget_level = {"经济": 1.6, "中等": 1.0, "舒适": 0.55, "豪华": 0.3}.get(budget, 1.0)
    scored = []
    for p in pois:
        fit = (fit_map or {}).get(p["name"], 80)
        s = score_poi(p, pref, fit, budget_level)
        item = dict(p)
        item["score"] = round(s, 1)
        item["weather_fit"] = fit
        scored.append(item)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def search(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """全局景点搜索（跨城市）。"""
    kw = keyword.strip()
    hits = []
    for c in _load_cities():
        for p in get_pois(c["id"]):
            hay = f'{p["name"]}{p["type"]}{"".join(p.get("tags", []))}{p["desc"]}'
            if kw in hay:
                hits.append({**p, "city": c["name"], "city_id": c["id"]})
    hits.sort(key=lambda x: x["heat"], reverse=True)
    return hits[:limit]
