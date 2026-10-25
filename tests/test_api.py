"""接口层测试：公开接口、鉴权拦截、账号全流程、分享。"""
from __future__ import annotations

import random


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["cities"] >= 20
    assert body["pois"] >= 150


def test_cities_and_pois(client):
    cities = client.get("/api/cities").json()["items"]
    assert len(cities) >= 20
    first = cities[0]["id"]
    detail = client.get(f"/api/cities/{first}/pois").json()
    assert detail["items"]


def test_plan_requires_login(client):
    r = client.post("/api/plan", json={"query": "贵阳3天"})
    assert r.status_code == 401


def test_revise_and_plans_require_login(client):
    assert client.post("/api/plan/revise", json={"plan": {}, "day": 1}).status_code == 401
    assert client.get("/api/plans").status_code == 401


def _register(client):
    email = f"pytest{random.randint(100000, 999999)}@163.com"
    code = client.post("/api/auth/code", json={"email": email}).json()
    if not code.get("code"):
        return None, None  # 配了真实 SMTP，跳过依赖验证码的用例
    r = client.post("/api/auth/register", json={
        "email": email, "password": "Test123456", "code": code["code"],
        "city_id": "guiyang", "nickname": "测试",
    })
    assert r.status_code == 200, r.text
    return email, r.json()["token"]


def test_reject_non_163_email(client):
    r = client.post("/api/auth/code", json={"email": "someone@gmail.com"})
    assert r.json()["ok"] is False


def test_auth_flow_and_share(client):
    email, token = _register(client)
    if not token:
        return
    h = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=h).json()["user"]["city_name"] == "贵阳"
    assert client.get("/api/auth/me").status_code == 401

    # 收藏行程
    payload = {"ok": True, "plan": {"city": "贵阳", "days": 2, "theme": "测试行程",
                                    "summary": "摘要", "itinerary": [{"day": 1, "items": []}]}}
    pid = client.post("/api/plans", json={"payload": payload}, headers=h).json()["id"]
    assert len(client.get("/api/plans", headers=h).json()["items"]) == 1

    # 分享
    share = client.post(f"/api/plans/{pid}/share", headers=h).json()
    assert share["ok"] and share["path"].startswith("/s/")
    public = client.get(f"/api/share/{share['token']}")
    assert public.status_code == 200
    assert public.json()["city"] == "贵阳"

    # 取消分享后公开接口应 404
    client.delete(f"/api/plans/{pid}/share", headers=h)
    assert client.get(f"/api/share/{share['token']}").status_code == 404

    # 删除
    assert client.delete(f"/api/plans/{pid}", headers=h).json()["ok"]


def test_reset_password(client):
    email, token = _register(client)
    if not token:
        return
    code = client.post("/api/auth/reset-code", json={"email": email}).json()
    if not code.get("code"):
        return
    r = client.post("/api/auth/reset", json={
        "email": email, "code": code["code"], "password": "NewPass123"})
    assert r.status_code == 200
    # 旧密码失效
    assert client.post("/api/auth/login",
                       json={"email": email, "password": "Test123456"}).status_code == 400
    # 新密码可用
    assert client.post("/api/auth/login",
                       json={"email": email, "password": "NewPass123"}).status_code == 200


def test_geo_nearest(client):
    body = client.get("/api/geo/nearest?lat=26.58&lon=106.71").json()
    assert body["city"]["id"] == "guiyang"
    assert body["distance_km"] < 40


def test_share_page_served(client):
    r = client.get("/s/whatever")
    assert r.status_code == 200
    assert "行程分享" in r.text


def test_usage_endpoint(client):
    body = client.get("/api/usage").json()
    assert "total_tokens" in body and "quota" in body
