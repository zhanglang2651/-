"""真实天气数据：Open-Meteo（免密钥、免注册、全球覆盖）。

设计要点：
1. 上游不可用时降级到「气候估算」，并在返回体里带 source 字段，绝不假装真实。
2. 结果走 TTL 缓存，30 分钟内不重复打上游。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import httpx

from app.services.cache import cache

API = "https://api.open-meteo.com/v1/forecast"

WMO: dict[int, tuple[str, str]] = {
    0: ("晴", "sun"), 1: ("大部晴朗", "sun"), 2: ("多云", "cloud"), 3: ("阴", "cloud"),
    45: ("有雾", "fog"), 48: ("雾凇", "fog"),
    51: ("毛毛雨", "rain"), 53: ("小雨", "rain"), 55: ("细雨", "rain"),
    56: ("冻雨", "rain"), 57: ("冻雨", "rain"),
    61: ("小雨", "rain"), 63: ("中雨", "rain"), 65: ("大雨", "rain"),
    66: ("冻雨", "rain"), 67: ("强冻雨", "rain"),
    71: ("小雪", "snow"), 73: ("中雪", "snow"), 75: ("大雪", "snow"), 77: ("雪粒", "snow"),
    80: ("阵雨", "rain"), 81: ("强阵雨", "rain"), 82: ("暴雨", "rain"),
    85: ("阵雪", "snow"), 86: ("强阵雪", "snow"),
    95: ("雷阵雨", "storm"), 96: ("雷暴冰雹", "storm"), 99: ("强雷暴", "storm"),
}


def describe(code: int) -> tuple[str, str]:
    return WMO.get(code, ("未知", "cloud"))


def _fallback(lat: float, lon: float, days: int) -> dict[str, Any]:
    """上游不可用时的气候估算（按纬度粗估），明确标记为估算。"""
    month = datetime.now().month
    base = 26 - abs(lat - 25) * 0.75
    seasonal = 8 if month in (6, 7, 8) else (-6 if month in (12, 1, 2) else 0)
    t = round(base + seasonal, 1)
    daily = []
    for i in range(days):
        daily.append({
            "date": datetime.fromordinal(datetime.now().toordinal() + i).strftime("%Y-%m-%d"),
            "t_max": round(t + 4 + i % 2, 1), "t_min": round(t - 3 - i % 2, 1),
            "rain_prob": 30, "code": 2, "text": "多云", "icon": "cloud", "uv": 6,
        })
    return {
        "source": "climate_estimate",
        "source_label": "气候估算（上游不可用）",
        "current": {"temp": t, "text": "多云", "icon": "cloud", "humidity": 65, "wind": 8, "code": 2},
        "daily": daily,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


async def fetch_weather(lat: float, lon: float, days: int = 7) -> dict[str, Any]:
    key = f"weather:{round(lat, 2)},{round(lon, 2)}:{days}"
    cached = cache.get(key)
    if cached:
        return cached

    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max",
        "timezone": "Asia/Shanghai", "forecast_days": days,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(API, params=params)
            r.raise_for_status()
            raw = r.json()

        cur = raw.get("current", {})
        ctext, cicon = describe(int(cur.get("weather_code", 2)))
        daily_raw = raw.get("daily", {})
        daily = []
        for i, d in enumerate(daily_raw.get("time", [])):
            code = int(daily_raw["weather_code"][i])
            text, icon = describe(code)
            daily.append({
                "date": d,
                "t_max": daily_raw["temperature_2m_max"][i],
                "t_min": daily_raw["temperature_2m_min"][i],
                "rain_prob": daily_raw["precipitation_probability_max"][i],
                "uv": daily_raw["uv_index_max"][i],
                "code": code, "text": text, "icon": icon,
            })
        result = {
            "source": "open-meteo",
            "source_label": "Open-Meteo 气象实况",
            "current": {
                "temp": cur.get("temperature_2m"),
                "text": ctext, "icon": cicon,
                "humidity": cur.get("relative_humidity_2m"),
                "wind": cur.get("wind_speed_10m"),
                "code": cur.get("weather_code"),
            },
            "daily": daily,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
        cache.set(key, result, 1800)
        return result
    except Exception:  # noqa: BLE001 - 任何上游异常都降级
        fb = _fallback(lat, lon, days)
        cache.set(key, fb, 300)
        return fb


def weather_fit(daily: dict[str, Any], indoor: bool) -> tuple[int, str]:
    """天气—场景适配分（0-100），用于热度模型与行程排序。"""
    rain = daily.get("rain_prob") or 0
    tmax = daily.get("t_max") or 25
    code = daily.get("code", 0)
    storm = code >= 95
    if storm or rain >= 80:
        return (92, "强降雨，室内项目体验更稳") if indoor else (38, "降水概率高，户外项目建议改期")
    if rain >= 55:
        return (85, "有阵雨，室内更稳妥") if indoor else (58, "可能有阵雨，建议带伞并压缩户外时长")
    if tmax >= 34:
        return (88, "高温时段，室内避暑合适") if indoor else (62, "午后高温，建议早晚出行")
    if tmax <= 5:
        return (86, "气温偏低，室内更舒适") if indoor else (66, "气温低，注意保暖")
    if rain <= 15 and 15 <= tmax <= 28:
        return (78, "天气尚可") if indoor else (98, "天气通透，户外正当时")
    return (76, "室内不受天气影响") if indoor else (86, "适合外出")


def best_day(daily: list[dict[str, Any]]) -> int:
    """挑出未来几天里最适合出游的一天（少雨、温度舒适优先）。"""
    if not daily:
        return 0
    def score(d: dict[str, Any]) -> float:
        rain = d.get("rain_prob") or 0
        tmax = d.get("t_max") or 25
        return -rain * 1.2 - abs(tmax - 24) * 0.8
    return max(range(len(daily)), key=lambda i: score(daily[i]))
