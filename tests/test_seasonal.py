"""时令模块测试：节气算法、主题聚合、矩阵与路线契约。"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:\文旅助手")

import pytest  # noqa: E402

from app.services.seasonal import (TERM_ORDER, _terms_of_year, current_term,  # noqa: E402
                                   festivals_now, food_cities, routes_now,
                                   season_matrix, theme_overview)


# ---------------------------------------------------------------- 节气算法
def test_2026_has_24_terms():
    assert len(_terms_of_year(2026)) == 24


def test_term_names_complete_and_unique():
    names = [t[0] for t in _terms_of_year(2026)]
    assert set(names) == set(TERM_ORDER)
    assert len(names) == len(set(names))


def test_term_dates_increasing():
    dates = [t[1] for t in _terms_of_year(2026)]
    assert dates == sorted(dates)


@pytest.mark.parametrize("name,truth", [
    ("小寒", "2026-01-05"), ("立春", "2026-02-04"), ("春分", "2026-03-20"),
    ("清明", "2026-04-05"), ("夏至", "2026-06-21"), ("秋分", "2026-09-23"),
    ("霜降", "2026-10-23"), ("立冬", "2026-11-07"), ("冬至", "2026-12-22"),
])
def test_key_terms_match_astronomy(name, truth):
    """对照紫金山天文台 2026 年节气时刻（日期级）。"""
    calc = dict(_terms_of_year(2026))
    assert calc.get(name) == truth


def test_adjacent_years_complete():
    assert len(_terms_of_year(2025)) == 24
    assert len(_terms_of_year(2027)) == 24


# ---------------------------------------------------------------- 当前节气
def test_current_term_fields():
    ct = current_term()
    for key in ("name", "date", "season", "pheno", "advice", "next", "next_date"):
        assert ct.get(key), f"缺字段 {key}"
    assert len(ct["year_terms"]) == 24


def test_current_term_timeline_consistent():
    ct = current_term()
    assert ct["date"] <= ct["today"]
    assert ct["next_date"] > ct["today"]
    assert ct["days_to_next"] >= 0


# ---------------------------------------------------------------- 主题聚合
def test_theme_count():
    assert len(theme_overview()) == 8


def test_every_theme_matches_some_city():
    counts = {t["id"]: t["total_cities"] for t in theme_overview()}
    assert all(v >= 1 for v in counts.values()), counts


def test_no_theme_matches_all_cities():
    """主题必须有区分度，不能出现「人人都是自然风光」。"""
    counts = {t["id"]: t["total_cities"] for t in theme_overview()}
    assert max(counts.values()) < 30, counts


def test_theme_fields_present():
    for t in theme_overview():
        assert t.get("name") and t.get("icon") and t.get("color")
        assert len(t["cities"]) <= 6


# ---------------------------------------------------------------- 风味
def test_food_list_non_empty():
    assert len(food_cities()) > 0


def test_food_entries_have_city_and_foods():
    for f in food_cities():
        assert f.get("city")
        assert isinstance(f.get("foods"), list)


def test_food_sorted_by_count_desc():
    foods = food_cities()
    counts = [len(f["foods"]) for f in foods]
    assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------- 路线
def test_routes_present():
    assert len(routes_now()) > 0


def test_routes_have_plan_fields():
    for r in routes_now():
        assert r.get("days") and r.get("budget") and r.get("route")
        assert r.get("tip")


def test_routes_mark_season():
    for r in routes_now():
        assert isinstance(r["in_season"], bool)
        assert r["season_hint"]


# ---------------------------------------------------------------- 矩阵
def test_matrix_covers_all_cities():
    assert len(season_matrix()["cities"]) == 30


def test_matrix_months_in_range():
    for c in season_matrix()["cities"]:
        assert all(1 <= m <= 12 for m in c["months"])


def test_matrix_current_month_valid():
    assert 1 <= season_matrix()["current_month"] <= 12


# ---------------------------------------------------------------- 节庆
def test_festivals_structure():
    for f in festivals_now():
        assert f.get("city") and f.get("name")
