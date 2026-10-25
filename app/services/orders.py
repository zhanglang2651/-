"""订单管理：车票 / 景区门票 / 酒店。

两类来源：
1. 用户手动录入
2. 从 AI 行程一键导入（门票按景点、住宿按天、城际交通按整体生成草稿单）
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from app.services import db

ORDER_TYPES = {"train": "车票", "ticket": "门票", "hotel": "酒店"}
STATUS = {"pending": "待支付", "paid": "已支付", "used": "已使用", "cancelled": "已取消"}

# A 线（跳转型）下单深链：先落到 OTA 搜索页，由用户完成支付
DEEP_LINKS = {
    "ctrip": "https://you.ctrip.com/searchsite/?keyword={kw}",
    "ctrip_train": "https://you.ctrip.com/train/",
    "ctrip_ticket": "https://you.ctrip.com/ticketdest/",
    "tongcheng_hotel": "https://www.ly.com/hotel/hotelsearch?keyword={kw}",
}


def buy_link(o: dict[str, Any]) -> str:
    """按订单类型生成 OTA 搜索/下单深链。"""
    kw = " ".join(x for x in [o.get("city") or "", o.get("title") or ""] if x).strip()
    t = o.get("type")
    if t == "hotel":
        return DEEP_LINKS["tongcheng_hotel"].format(kw=quote(kw))
    if t == "train":
        return DEEP_LINKS["ctrip_train"].format(kw=quote(kw))
    if t == "ticket":
        return DEEP_LINKS["ctrip_ticket"].format(kw=quote(kw))
    return DEEP_LINKS["ctrip"].format(kw=quote(kw))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _norm_type(t: str) -> str:
    return t if t in ORDER_TYPES else "ticket"


def _norm_status(s: str) -> str:
    return s if s in STATUS else "pending"


def create(user_id: int, data: dict[str, Any]) -> str:
    oid = uuid.uuid4().hex[:12]
    db.execute(
        "INSERT INTO orders (id,user_id,type,title,city,detail,amount,quantity,travel_date,"
        "status,plan_id,note,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (oid, user_id, _norm_type(data.get("type", "")),
         (data.get("title") or "未命名").strip()[:80],
         (data.get("city") or "").strip()[:30],
         (data.get("detail") or "").strip()[:200],
         float(data.get("amount") or 0),
         max(1, int(data.get("quantity") or 1)),
         (data.get("travel_date") or "").strip()[:20],
         _norm_status(data.get("status", "pending")),
         data.get("plan_id") or "", (data.get("note") or "").strip()[:200], _now()),
    )
    return oid


def list_orders(user_id: int, order_type: str = "") -> list[dict[str, Any]]:
    sql = ("SELECT id,type,title,city,detail,amount,quantity,travel_date,status,plan_id,"
           "note,created_at FROM orders WHERE user_id=?")
    args: list[Any] = [user_id]
    if order_type:
        sql += " AND type=?"
        args.append(_norm_type(order_type))
    sql += " ORDER BY COALESCE(NULLIF(travel_date,''), created_at) DESC, created_at DESC"
    rows = db.query_all(sql, tuple(args))
    for r in rows:
        r["type_label"] = ORDER_TYPES.get(r["type"], "其他")
        r["status_label"] = STATUS.get(r["status"], r["status"])
        r["buy_url"] = r.get("pay_url") or buy_link(r)
    return rows


def update_status(user_id: int, order_id: str, status: str) -> bool:
    row = db.query_one("SELECT id FROM orders WHERE id=? AND user_id=?", (order_id, user_id))
    if not row:
        return False
    db.execute("UPDATE orders SET status=? WHERE id=?", (_norm_status(status), order_id))
    return True


def delete(user_id: int, order_id: str) -> bool:
    row = db.query_one("SELECT id FROM orders WHERE id=? AND user_id=?", (order_id, user_id))
    if not row:
        return False
    db.execute("DELETE FROM orders WHERE id=?", (order_id,))
    return True


def summary(user_id: int) -> dict[str, Any]:
    rows = db.query_all("SELECT type,amount,status,created_at FROM orders WHERE user_id=?",
                        (user_id,))
    month = datetime.now().strftime("%Y-%m")
    valid = [r for r in rows if r["status"] != "cancelled"]
    return {
        "month_amount": round(sum(r["amount"] for r in valid if (r["created_at"] or "")[:7] == month), 2),
        "total_amount": round(sum(r["amount"] for r in valid), 2),
        "pending": sum(1 for r in rows if r["status"] == "pending"),
        "paid": sum(1 for r in rows if r["status"] == "paid"),
        "used": sum(1 for r in rows if r["status"] == "used"),
        "cancelled": sum(1 for r in rows if r["status"] == "cancelled"),
        "total": len(rows),
        "by_type": {t: sum(1 for r in rows if r["type"] == t) for t in ORDER_TYPES},
    }


def import_from_plan(user_id: int, payload: dict[str, Any], plan_id: str = "") -> dict[str, Any]:
    """把一份行程拆成订单草稿：城际交通 / 每个收费景点 / 每晚住宿。"""
    plan = payload.get("plan") or {}
    brief = payload.get("brief") or {}
    city = plan.get("city") or ""
    days = plan.get("itinerary") or []
    if not days:
        return {"ok": False, "message": "行程内容为空，无法生成订单"}
    if plan_id:
        exist = db.query_one("SELECT COUNT(*) AS c FROM orders WHERE user_id=? AND plan_id=?",
                             (user_id, plan_id))
        if exist and exist["c"] > 0:
            return {"ok": False, "message": "这份行程已经生成过订单了"}

    created: list[str] = []
    breakdown = (plan.get("budget") or {}).get("breakdown") or {}

    # 1) 城际交通
    inter = float(breakdown.get("城际交通") or 0)
    if inter > 0:
        origin = brief.get("origin") or "出发地"
        created.append(create(user_id, {
            "type": "train", "title": f"{origin} → {city} 往返交通", "city": city,
            "detail": f"{brief.get('people', 2)} 人 · {plan.get('days', len(days))} 天行程",
            "amount": inter, "quantity": int(brief.get("people", 2)),
            "travel_date": (days[0].get("date") or ""), "status": "pending",
            "plan_id": plan_id, "note": "由 AI 行程自动生成",
        }))

    # 2) 景点门票（只导收费景点）
    for d in days:
        for it in (d.get("items") or []):
            cost = float(it.get("cost") or 0)
            if cost <= 0:
                continue
            created.append(create(user_id, {
                "type": "ticket", "title": it.get("name", "景区门票"), "city": city,
                "detail": f'{d.get("date", "")} {it.get("time", "")} 入园 · {it.get("type", "")}',
                "amount": cost, "quantity": int(brief.get("people", 2)),
                "travel_date": d.get("date") or "", "status": "pending",
                "plan_id": plan_id, "note": "由 AI 行程自动生成",
            }))

    # 3) 住宿（按夜均摊）
    stay_total = float(breakdown.get("住宿") or 0)
    nights = max(0, len(days) - 1)
    if stay_total > 0 and nights > 0:
        per_night = round(stay_total / nights, 2)
        for i in range(nights):
            d = days[i]
            created.append(create(user_id, {
                "type": "hotel", "title": d.get("stay") or f"{city} 市区住宿", "city": city,
                "detail": f'第 {i + 1} 晚 · {d.get("date", "")} 入住',
                "amount": per_night, "quantity": 1,
                "travel_date": d.get("date") or "", "status": "pending",
                "plan_id": plan_id, "note": "由 AI 行程自动生成",
            }))

    return {"ok": True, "count": len(created), "ids": created}
