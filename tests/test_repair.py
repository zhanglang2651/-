"""规则修补与校验分级测试。"""
from __future__ import annotations

import copy

from app.agents.graph import _fix_budget, _rule_repair, validate
from app.services import poi as poi_svc

CITY = poi_svc.get_city("guiyang")
CANDS = poi_svc.get_pois("guiyang")


def _bad_plan():
    return {
        "city": "贵阳", "days": 2, "summary": "测试行程",
        "budget": {"total": 999, "breakdown": {"住宿": 380, "餐饮": 300}},
        "itinerary": [
            {"day": 1, "date": "2026-10-26", "title": "第一天", "items": [
                {"time": "09:00", "name": "贵阳市规划馆", "type": "人文", "hours": 2, "cost": 0},
                {"time": "14:00", "name": "黔灵山公园", "type": "自然", "hours": 3, "cost": 5},
                {"time": "17:00", "name": "黔灵山公园", "type": "自然", "hours": 3, "cost": 5},
            ], "meals": [{"time": "12:00", "name": "肠旺面", "place": "市区", "cost": 30}]},
            {"day": 2, "date": "2026-10-27", "title": "第二天", "items": [], "meals": []},
        ],
    }


def test_validate_flags_hallucination_as_error():
    errors, _ = validate(_bad_plan(), 2, CANDS)
    assert any("不在候选池" in e for e in errors)


def test_validate_downgrades_single_spot_to_warning():
    plan = {
        "city": "贵阳", "days": 1, "summary": "s",
        "budget": {"total": 100, "breakdown": {"住宿": 100}},
        "itinerary": [{"day": 1, "date": "2026-10-26", "title": "t", "items": [
            {"time": "09:00", "name": "黔灵山公园", "type": "自然", "hours": 3, "cost": 5}],
            "meals": [{"time": "12:00", "name": "x", "place": "y", "cost": 30}]}],
    }
    errors, warnings = validate(plan, 1, CANDS)
    assert errors == []
    assert any("节奏偏松" in w for w in warnings)


def test_rule_repair_removes_hallucination_and_dup():
    fixed = _rule_repair(copy.deepcopy(_bad_plan()), CANDS, CITY, 2)
    errors, _ = validate(fixed, 2, CANDS)
    names = [it["name"] for d in fixed["itinerary"] for it in d["items"]]
    assert errors == []
    assert len(names) == len(set(names)), "修补后不应有重复景点"
    assert all(n in {c["name"] for c in CANDS} for n in names)


def test_rule_repair_fills_empty_day():
    fixed = _rule_repair(copy.deepcopy(_bad_plan()), CANDS, CITY, 2)
    day2 = fixed["itinerary"][1]
    assert len(day2["items"]) >= 2
    assert len(day2["meals"]) == 3


def test_fix_budget_makes_total_consistent():
    plan = {"budget": {"total": 9999, "breakdown": {"住宿": 380, "餐饮": 300}}}
    _fix_budget(plan)
    assert plan["budget"]["total"] == 680
