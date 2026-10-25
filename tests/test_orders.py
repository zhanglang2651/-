"""订单功能测试：CRUD、状态流转、从行程导入、汇总统计。"""
from __future__ import annotations

import random


def _login(client):
    email = f"ord{random.randint(100000, 999999)}@163.com"
    code = client.post("/api/auth/code", json={"email": email}).json()
    if not code.get("code"):
        return None
    r = client.post("/api/auth/register", json={
        "email": email, "password": "Test123456", "code": code["code"],
        "city_id": "guiyang", "nickname": "订单测试"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_orders_require_login(client):
    assert client.get("/api/orders").status_code == 401
    assert client.post("/api/orders", json={"title": "x"}).status_code == 401


def test_order_crud_and_summary(client):
    h = _login(client)
    if not h:
        return

    r = client.post("/api/orders", json={
        "type": "ticket", "title": "黄果树瀑布门票", "city": "安顺",
        "travel_date": "2026-11-02", "amount": 160, "quantity": 2,
        "detail": "成人票"})
    assert r.status_code == 200
    oid = r.json()["id"]

    rows = client.get("/api/orders", headers=h).json()
    assert len(rows["items"]) == 1
    assert rows["items"][0]["type_label"] == "门票"
    assert rows["summary"]["pending"] == 1
    assert rows["summary"]["total_amount"] == 160

    # 筛选
    assert len(client.get("/api/orders?type=ticket", headers=h).json()["items"]) == 1
    assert len(client.get("/api/orders?type=hotel", headers=h).json()["items"]) == 0

    # 状态流转
    assert client.patch(f"/api/orders/{oid}", json={"status": "paid"}, headers=h).json()["ok"]
    assert client.get("/api/orders", headers=h).json()["summary"]["paid"] == 1
    client.patch(f"/api/orders/{oid}", json={"status": "used"}, headers=h)
    assert client.get("/api/orders", headers=h).json()["summary"]["used"] == 1

    assert client.delete(f"/api/orders/{oid}", headers=h).json()["ok"]
    assert client.get("/api/orders", headers=h).json()["summary"]["total"] == 0


def test_import_from_plan(client):
    h = _login(client)
    if not h:
        return

    payload = {
        "ok": True,
        "brief": {"people": 2, "origin": "成都"},
        "plan": {
            "city": "贵阳", "days": 2,
            "budget": {"total": 2000, "breakdown": {
                "住宿": 760, "餐饮": 600, "门票": 45, "市内交通": 200, "城际交通": 395}},
            "itinerary": [
                {"day": 1, "date": "2026-11-01", "stay": "观山湖区",
                 "items": [{"time": "09:00", "name": "黔灵山公园", "cost": 5},
                           {"time": "14:00", "name": "贵州省博物馆", "cost": 0}]},
                {"day": 2, "date": "2026-11-02", "stay": "观山湖区",
                 "items": [{"time": "09:00", "name": "天河潭", "cost": 40}]},
            ],
        },
    }
    r = client.post("/api/orders/import", json={"payload": payload, "plan_id": "p1"}, headers=h)
    assert r.status_code == 200, r.text
    # 1 城际 + 2 收费门票 + 1 晚住宿 = 4
    assert r.json()["count"] == 4

    rows = client.get("/api/orders", headers=h).json()["items"]
    types = sorted(o["type"] for o in rows)
    assert types == ["hotel", "ticket", "ticket", "train"]
    # 住宿按晚均摊：760 / 1 晚
    hotel = next(o for o in rows if o["type"] == "hotel")
    assert hotel["amount"] == 760

    # 同一 plan 不能重复导入
    again = client.post("/api/orders/import", json={"payload": payload, "plan_id": "p1"}, headers=h)
    assert again.status_code == 400
