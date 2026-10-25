"""景点图片与交通住宿服务测试。"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:\文旅助手")

import pytest  # noqa: E402

from app.services import poi_photos as pps  # noqa: E402
from app.services.transport import query_hotels, query_trains  # noqa: E402


# ---------------------------------------------------------------- 检索词
def test_poi_queries_cover_all_pois():
    """每个景点都应该有英文检索词（否则点了没图）。"""
    from app.services import poi as poi_svc
    q = pps._queries()
    missing = []
    for c in poi_svc.list_cities():
        for p in poi_svc.get_pois(c["id"]):
            if not q.get(c["id"], {}).get(p["name"]):
                missing.append(f'{c["name"]}/{p["name"]}')
    # 允许少量缺口（模型偶尔会失败），但不能超过 15%
    total = sum(len(poi_svc.get_pois(c["id"])) for c in poi_svc.list_cities())
    assert len(missing) <= total * 0.15, f"缺口过多: {missing[:20]}"


def test_poi_queries_are_pure_english():
    """检索词不能含中文字符——Unsplash 搜中文搜不到东西。"""
    bad = []
    for cid, pois in pps._queries().items():
        for name, queries in pois.items():
            for q in queries:
                if any("一" <= ch <= "鿿" for ch in q):
                    bad.append(f"{cid}/{name}: {q}")
    assert not bad, bad[:15]


def test_poi_queries_not_too_generic():
    """兜底词不能过于宽泛，否则搜出来的图跟景点无关。"""
    generic = {"park", "bridge", "garden", "museum", "meeting", "marketplace",
               "sunset", "waterfall", "ancient town", "night market", "temple",
               "old town", "lake", "mountain", "scenery", "food", "market",
               "street", "building", "view", "landscape"}
    bad = []
    for cid, pois in pps._queries().items():
        for name, queries in pois.items():
            for q in queries:
                if q.strip().lower() in generic:
                    bad.append(f"{cid}/{name}: {q}")
    assert not bad, bad[:15]


def test_poi_manifest_roundtrip():
    """manifest 读写应保持结构。"""
    assert isinstance(pps.load_manifest("guiyang"), dict)
    assert isinstance(pps.public_poi_photos("guiyang", "不存在的景点"), list)


# ---------------------------------------------------------------- 交通
def test_train_query_basic():
    r = query_trains("贵阳", "重庆")
    assert r["ok"] is True
    assert r["origin"] == "贵阳" and r["dest"] == "重庆"
    assert r["distance_km"] > 0
    assert r["options"], "应有交通方案"
    assert r["links"]["12306_query"]


def test_train_query_default_date_is_tomorrow():
    from datetime import date, timedelta
    r = query_trains("贵阳", "重庆")
    expect = (date.today() + timedelta(days=1)).isoformat()
    assert r["travel_date"] == expect


def test_train_query_rejects_same_city():
    r = query_trains("贵阳", "贵阳")
    assert r["ok"] is False
    assert "同城" in r["message"]


def test_train_query_rejects_unknown_city():
    r = query_trains("贵阳", "火星")
    assert r["ok"] is False
    assert "未收录" in r["message"]


def test_train_query_has_disclaimer():
    """必须声明这是推算值而非实时库存——这是数据诚信底线。"""
    r = query_trains("北京", "上海")
    assert "12306" in r["disclaimer"]
    assert "推算" in r["data_note"]


def test_train_short_distance_no_flight():
    """800km 以内不该推荐飞机（高铁更快更省心）。"""
    r = query_trains("贵阳", "重庆")
    modes = " ".join(o["mode"] for o in r["options"])
    assert "飞机" not in modes


def test_train_long_distance_has_flight():
    r = query_trains("北京", "拉萨")
    modes = " ".join(o["mode"] for o in r["options"])
    assert "飞机" in modes


def test_train_options_have_required_fields():
    r = query_trains("上海", "杭州")
    for o in r["options"]:
        assert o["mode"] and o["duration"] and o["price"] and o["note"]
        assert o.get("kind")


# ---------------------------------------------------------------- 住宿
def test_hotel_query_basic():
    h = query_hotels("贵阳")
    assert h["ok"] is True
    assert h["city"] == "贵阳"
    assert h["areas"], "应推荐住宿区域"
    assert h["price_band"]
    assert h["links"]["ctrip"]


def test_hotel_near_poi_prioritizes_area():
    """指定景点后，该景点对应的区域应排到最前。"""
    h = query_hotels("苏州", near_poi="拙政园")
    assert h["ok"] is True
    assert h["areas"][0]["nearby"][0] == "拙政园"


def test_hotel_areas_use_real_pois():
    """推荐区域的锚点必须是知识库里真实存在的景点。"""
    from app.services import poi as poi_svc
    h = query_hotels("重庆")
    real = {p["name"] for p in poi_svc.get_pois("chongqing")}
    for a in h["areas"]:
        for n in a["nearby"]:
            assert n in real, f"{n} 不在重庆景点库中"


def test_hotel_rooms_calculation():
    """3 人住 2 间，2 人住 1 间。"""
    assert query_hotels("贵阳", people=3)["rooms_needed"] == 2
    assert query_hotels("贵阳", people=2)["rooms_needed"] == 1
    assert query_hotels("贵阳", people=1)["rooms_needed"] == 1


def test_hotel_rejects_unknown_city():
    h = query_hotels("火星")
    assert h["ok"] is False


def test_hotel_has_disclaimer():
    """必须声明不含实时房价。"""
    h = query_hotels("贵阳")
    assert "实时房价" in h["data_note"]
    assert "不提供具体酒店报价" in h["disclaimer"]
