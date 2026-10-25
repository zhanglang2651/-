"""热度模型与天气适配的单元测试。"""
from __future__ import annotations

from datetime import date

from app.services import budget as budget_svc
from app.services import poi as poi_svc
from app.services import trends as trend_svc
from app.services import weather as weather_svc
from app.services.ratelimit import SlidingWindow


def test_parse_season_ranges():
    assert trend_svc.parse_season("5-10月") == {5, 6, 7, 8, 9, 10}
    both = trend_svc.parse_season("3-5月 / 9-11月")
    assert both == {3, 4, 5, 9, 10, 11}
    assert trend_svc.parse_season("") == set(range(1, 13))


def test_weather_fit_rain_favours_indoor():
    rainy = {"rain_prob": 90, "t_max": 20, "code": 63}
    indoor_fit, _ = weather_svc.weather_fit(rainy, indoor=True)
    outdoor_fit, _ = weather_svc.weather_fit(rainy, indoor=False)
    assert indoor_fit > outdoor_fit
    assert outdoor_fit < 50


def test_weather_fit_sunny_favours_outdoor():
    sunny = {"rain_prob": 5, "t_max": 24, "code": 1}
    indoor_fit, _ = weather_svc.weather_fit(sunny, indoor=True)
    outdoor_fit, _ = weather_svc.weather_fit(sunny, indoor=False)
    assert outdoor_fit > indoor_fit


def test_calendar_weekend_factor():
    sat = date(2026, 10, 24)
    info = trend_svc.calendar_info(sat)
    assert info["is_weekend"] is True
    assert info["factor"] == 88


def test_heat_levels_are_ordered():
    assert trend_svc.heat_level(95)[0] == "爆满"
    assert trend_svc.heat_level(80)[0] == "高热"
    assert trend_svc.heat_level(70)[0] == "温热"
    assert trend_svc.heat_level(30)[0] == "平稳"


def test_compute_is_sorted_and_bounded():
    city = poi_svc.get_city("guiyang")
    daily = {"rain_prob": 20, "t_max": 24, "code": 1}
    items = trend_svc.compute(city, daily)
    heats = [i["heat_now"] for i in items]
    assert heats == sorted(heats, reverse=True)
    assert all(20 <= h <= 99 for h in heats)
    assert [i["rank"] for i in items] == list(range(1, len(items) + 1))


def test_rain_lifts_indoor_attraction():
    """同一天气下，室内景点在雨天的排序应比晴天更靠前。"""
    city = poi_svc.get_city("guiyang")
    rainy = {"rain_prob": 95, "t_max": 18, "code": 65}
    sunny = {"rain_prob": 0, "t_max": 24, "code": 0}
    r_rank = {i["name"]: i["rank"] for i in trend_svc.compute(city, rainy)}
    s_rank = {i["name"]: i["rank"] for i in trend_svc.compute(city, sunny)}
    assert r_rank["贵州省博物馆"] < s_rank["贵州省博物馆"]


def test_budget_intercity_by_distance():
    far = budget_svc.intercity("贵阳", "北京", 2)
    near = budget_svc.intercity("贵阳", "安顺", 2)
    assert far["cost"] > near["cost"]
    assert far["per_person"] == 1200
    same = budget_svc.intercity("贵阳", "贵阳", 2)
    assert same["cost"] == 0


def test_budget_total_equals_breakdown():
    est = budget_svc.estimate(days=3, people=2, level="中等",
                              origin="贵阳", dest="成都", tickets=150)
    assert est["total"] == sum(est["breakdown"].values())
    assert est["breakdown"]["门票"] == 150


def test_rate_limiter_blocks_after_quota():
    w = SlidingWindow()
    for _ in range(3):
        ok, _wait = w.allow("k", 3, 60)
        assert ok
    blocked, wait = w.allow("k", 3, 60)
    assert blocked is False
    assert wait > 0
    # 不同 key 互不影响
    assert w.allow("other", 3, 60)[0] is True
