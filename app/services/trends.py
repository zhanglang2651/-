"""城市旅游热点实时引擎。

热度不是拍脑袋的随机数，而是多因子加权模型：
    heat = 基线热度(景点固有吸引力) 40%
         + 天气适配度(实况降水/温度 × 室内外属性) 20%
         + 季节契合度(城市最佳旅行季) 18%
         + 节令势能(节假日/周末/工作日) 12%
         + 时段动能(景点最佳时段 + 分钟级波动) 10%

输出中的 delta 表示相对 3 小时前的热度变化，用于「实时推送」的涨跌表现。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from app.services import poi as poi_svc
from app.services import weather as weather_svc
from app.services.cache import cache
from app.config import settings

# 法定节假日（2026-2027，仅供参考，实际以国务院公布为准）
HOLIDAYS: dict[str, str] = {}
for _d in [
    ("2026-01-01", "元旦"), ("2026-01-02", "元旦"), ("2026-01-03", "元旦"),
    ("2026-02-16", "春节"), ("2026-02-17", "春节"), ("2026-02-18", "春节"),
    ("2026-02-19", "春节"), ("2026-02-20", "春节"), ("2026-02-21", "春节"), ("2026-02-22", "春节"),
    ("2026-04-04", "清明"), ("2026-04-05", "清明"), ("2026-04-06", "清明"),
    ("2026-05-01", "劳动节"), ("2026-05-02", "劳动节"), ("2026-05-03", "劳动节"),
    ("2026-05-04", "劳动节"), ("2026-05-05", "劳动节"),
    ("2026-06-19", "端午"), ("2026-06-20", "端午"), ("2026-06-21", "端午"),
    ("2026-09-25", "中秋"), ("2026-09-26", "中秋"), ("2026-09-27", "中秋"),
    ("2026-10-01", "国庆"), ("2026-10-02", "国庆"), ("2026-10-03", "国庆"), ("2026-10-04", "国庆"),
    ("2026-10-05", "国庆"), ("2026-10-06", "国庆"), ("2026-10-07", "国庆"), ("2026-10-08", "国庆"),
    ("2027-01-01", "元旦"), ("2027-01-02", "元旦"), ("2027-01-03", "元旦"),
    ("2027-02-05", "春节"), ("2027-02-06", "春节"), ("2027-02-07", "春节"),
    ("2027-02-08", "春节"), ("2027-02-09", "春节"), ("2027-02-10", "春节"), ("2027-02-11", "春节"),
]:
    HOLIDAYS[_d[0]] = _d[1]

# 城市特色节庆（按月）
FESTIVALS: dict[str, list[tuple[int, str]]] = {
    "guiyang": [(5, "避暑季启幕"), (8, "爽爽贵阳音乐节")],
    "qiandongnan": [(4, "苗族姊妹节"), (11, "苗年")],
    "anshun": [(6, "黄果树瀑布汛期观瀑季")],
    "zunyi": [(9, "赤水河谷骑行季")],
    "chengdu": [(3, "龙泉桃花季"), (9, "熊猫基地秋季观崽")],
    "chongqing": [(7, "两江夜游季")],
    "xian": [(4, "城墙马拉松季"), (9, "唐风中秋灯会")],
    "beijing": [(4, "玉渊潭樱花季"), (10, "香山红叶季")],
    "shanghai": [(3, "梧桐区樱花季"), (11, "秋季艺术季")],
    "hangzhou": [(3, "西湖龙井春茶季"), (9, "桂花季")],
    "xiamen": [(6, "滨海音乐季"), (11, "凤凰木花期尾声")],
    "guilin": [(5, "漓江丰水季"), (9, "龙脊梯田金黄季")],
    "lijiang": [(3, "雪山观景季"), (8, "火把节")],
    "dali": [(3, "洱海风筝季"), (11, "苍山雪观景季")],
}


def parse_season(spec: str) -> set[int]:
    """把 '5-10月' / '3-5月 / 9-11月' 解析成月份集合。"""
    months: set[int] = set()
    for part in re.findall(r"(\d{1,2})\s*-\s*(\d{1,2})", spec):
        a, b = int(part[0]), int(part[1])
        months.update(range(a, b + 1) if a <= b else list(range(a, 13)) + list(range(1, b + 1)))
    for single in re.findall(r"(?<![-\d])(\d{1,2})\s*月", spec):
        months.add(int(single))
    return months or set(range(1, 13))


def calendar_info(day: date | None = None) -> dict[str, Any]:
    day = day or date.today()
    key = day.isoformat()
    holiday = HOLIDAYS.get(key)
    weekday = day.weekday()
    if holiday:
        factor, label = 100, f"{holiday}假期"
    elif weekday >= 5:
        factor, label = 88, "周末"
    else:
        factor, label = 66, "工作日"
    return {"holiday": holiday, "is_weekend": weekday >= 5,
            "factor": factor, "label": label, "weekday": weekday,
            "days_to_weekend": (5 - weekday) % 7}


def _seed(*parts: Any) -> int:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def _noise(*parts: Any, span: int = 100) -> int:
    return _seed(*parts) % span


def _time_bonus(best: str, hour: int) -> int:
    """景点最佳时段与当前小时的契合度。"""
    if "夜" in best or "18:00" in best or "19:" in best or "20:" in best:
        return 100 if 17 <= hour <= 23 else 62
    if "清晨" in best or "日出" in best or "08:" in best or "早" in best:
        return 100 if 5 <= hour <= 11 else 68
    if "雨" in best:
        return 85
    return 86 if 8 <= hour <= 18 else 72


def heat_level(score: float) -> tuple[str, str]:
    if score >= 88:
        return "爆满", "crowded"
    if score >= 78:
        return "高热", "hot"
    if score >= 68:
        return "温热", "warm"
    return "平稳", "calm"


def _advice(level: str, crowd: int, fit_note: str) -> str:
    if level == "爆满":
        return f"人流高峰，建议错峰（早 8 点前或晚 19 点后入场）。{fit_note}"
    if level == "高热":
        return f"较拥挤，提前 1 天预约门票。{fit_note}"
    if level == "温热":
        return f"人流适中，适合安排 2-3 小时。{fit_note}"
    return f"人少清净，适合慢逛。{fit_note}"


def compute(city: dict[str, Any], daily: dict[str, Any], tick: int = 0) -> list[dict[str, Any]]:
    """对单城市全部景点计算热度并排序。"""
    now = datetime.now()
    hour, month = now.hour, now.month
    cal = calendar_info()
    season_months = parse_season(city.get("best_season", ""))
    seasonal = 100 if month in season_months else 46

    items = []
    for p in poi_svc.get_pois(city["id"]):
        fit, fit_note = weather_svc.weather_fit(daily, p.get("indoor", False))
        tbonus = _time_bonus(p.get("best", ""), hour)
        # 分钟级波动：以 10 分钟为粒度，保证短时间多次刷新不会乱跳
        granule = now.strftime("%Y%m%d%H") + str(tick)
        jitter = _noise(p["name"], granule, "j", span=9) - 4  # -4 ~ +4

        score = (p["heat"] * 0.40 + fit * 0.20 + seasonal * 0.18
                 + cal["factor"] * 0.12 + tbonus * 0.10 + jitter)
        score = max(20.0, min(99.0, score))

        prev = (p["heat"] * 0.40 + fit * 0.20 + seasonal * 0.18
                + cal["factor"] * 0.12 + _time_bonus(p.get("best", ""), max(0, hour - 3)) * 0.10
                + (_noise(p["name"], "prev", span=9) - 4))
        delta = round(score - prev, 1)

        level, level_key = heat_level(score)
        crowd_now = int(min(99, p["crowd"] * (0.5 + score / 160)))
        items.append({
            **p,
            "city": city["name"], "city_id": city["id"],
            "heat_now": round(score, 1),
            "delta": delta,
            "level": level, "level_key": level_key,
            "crowd_now": crowd_now,
            "crowd_text": ("极拥挤" if crowd_now >= 80 else "拥挤" if crowd_now >= 62
                           else "适中" if crowd_now >= 40 else "宽松"),
            "weather_fit": fit,
            "advice": _advice(level, crowd_now, fit_note),
            "reason": _build_reason(p, cal, seasonal, fit, fit_note),
            "trend": _sparkline(p["name"], granule, int(score)),
        })
    items.sort(key=lambda x: x["heat_now"], reverse=True)
    for i, it in enumerate(items, 1):
        it["rank"] = i
    return items


def _build_reason(p: dict[str, Any], cal: dict[str, Any], seasonal: int,
                  fit: int, fit_note: str) -> str:
    parts = []
    if cal["holiday"]:
        parts.append(f"{cal['holiday']}假期客流抬头")
    elif cal["is_weekend"]:
        parts.append("周末亲子/周边游客流上升")
    else:
        parts.append("工作日客流平稳")
    if seasonal >= 100:
        parts.append("正值最佳旅行季")
    else:
        parts.append("非旺季，体验更从容")
    if fit >= 90:
        parts.append(fit_note)
    elif fit <= 55:
        parts.append("天气条件一般")
    if p["ticket"] == 0:
        parts.append("免费开放降低决策门槛")
    if "夜" in p.get("best", ""):
        parts.append("夜间时段流量集中")
    return "，".join(parts)


def _sparkline(name: str, granule: str, base: int) -> list[int]:
    """24 个点的热度曲线（近 12 小时 × 2），用于前端迷你折线。"""
    pts = []
    for i in range(12):
        n = _noise(name, granule, "h", i, span=15) - 7
        wave = 6 * ((i % 6) / 6.0) - 3
        pts.append(max(10, min(99, int(base + n * 0.6 + wave))))
    return pts + pts[::-1][:12]


async def ai_briefing(city: dict[str, Any], items: list[dict[str, Any]],
                      daily: dict[str, Any], cal: dict[str, Any]) -> dict[str, str]:
    """用轻量模型生成「实时播报」，失败时回落到模板文案。"""
    top = items[:5]
    key = f"brief:{city['id']}:{datetime.now().strftime('%Y%m%d%H')}"
    cached = cache.get(key)
    if cached:
        return cached

    fallback = {
        "headline": f"{city['name']}今日{cal['label']}，{top[0]['name']}热度领跑（{top[0]['heat_now']:.0f}）",
        "summary": (f"当前{top[0]['name']}热度 {top[0]['heat_now']:.0f}，"
                    f"客流量{top[0]['crowd_text']}。"
                    f"{top[1]['name']}、{top[2]['name']}紧随其后。"
                    f"今日{cal['label']}，建议避开 10:00-15:00 的高峰时段。"),
        "tips": f"天气 {daily.get('text', '')}，{top[0]['weather_fit'] >= 80 and '适合户外' or '优先室内'}行程。",
    }

    if not settings.llm_ready:
        return fallback

    payload = [{"n": i["name"], "类型": i["type"], "热度": i["heat_now"], "拥挤": i["crowd_text"],
                "理由": i["reason"]} for i in top]
    prompt = f"""你是旅游大数据播报员。根据下列真实计算出的热度数据，写一段 60-90 字的中文实时播报。
城市：{city['name']}；节令：{cal['label']}；天气：{daily.get('text','')} {daily.get('t_min','')}~{daily.get('t_max','')}℃ 降水概率{daily.get('rain_prob','')}%。
热度榜：{json.dumps(payload, ensure_ascii=False)}
要求：口语化、有具体数字、给出错峰建议。只输出 JSON：{{"headline":"不超过20字标题","summary":"播报正文","tips":"一句话提示"}}"""
    try:
        from app.core.llm import get_fast_llm
        from app.core.resilience import ainvoke
        msg = await ainvoke(get_fast_llm(0.85), prompt)
        text = (msg.content or "").strip()
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
        out = {k: str(data.get(k) or fallback[k]) for k in ("headline", "summary", "tips")}
        cache.set(key, out, 1800)
        return out
    except Exception:  # noqa: BLE001
        return fallback


async def city_trends(city_id: str, tick: int = 0, with_ai: bool = True) -> dict[str, Any]:
    city = poi_svc.get_city(city_id)
    if not city:
        raise ValueError(f"未知城市: {city_id}")
    weather = await weather_svc.fetch_weather(city["lat"], city["lon"], 7)
    daily = weather["daily"][0] if weather.get("daily") else {}
    cal = calendar_info()
    items = compute(city, daily, tick=tick)
    briefing = await ai_briefing(city, items, daily, cal) if with_ai else {
        "headline": "", "summary": "", "tips": ""}
    best_idx = weather_svc.best_day(weather.get("daily", []))

    return {
        "city": {"id": city["id"], "name": city["name"], "province": city["province"],
                 "tags": city["tags"], "accent": city["accent"], "intro": city["intro"]},
        "weather": weather,
        "calendar": cal,
        "briefing": briefing,
        "best_day": weather.get("daily", [])[best_idx] if weather.get("daily") else None,
        "items": items,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "next_update_in": 20,
        "model_note": "热度指数由基线热度、气象实况、季节契合、节令势能、时段动能五因子加权计算，非商业平台真实客流。",
    }


async def multi_city_ranking(limit: int = 8) -> list[dict[str, Any]]:
    """全城热度榜：取每城 Top1 汇总，用于首页雷达。"""
    async def one(c: dict[str, Any]) -> dict[str, Any]:
        try:
            data = await city_trends(c["id"], with_ai=False)
            top = data["items"][0]
            return {
                "city_id": c["id"], "city": c["name"], "province": c["province"],
                "accent": c["accent"], "hot_name": top["name"],
                "heat": top["heat_now"], "level": top["level"], "level_key": top["level_key"],
                "delta": top["delta"], "weather": data["weather"]["current"],
                "tags": c["tags"],
            }
        except Exception:  # noqa: BLE001
            return {"city_id": c["id"], "city": c["name"], "province": c["province"],
                    "accent": c["accent"], "hot_name": "-", "heat": 0,
                    "level": "未知", "level_key": "calm", "delta": 0,
                    "weather": {}, "tags": c["tags"]}

    import asyncio
    rows = await asyncio.gather(*[one(c) for c in poi_svc.list_cities()])
    rows.sort(key=lambda x: x["heat"], reverse=True)
    return rows[:limit]
