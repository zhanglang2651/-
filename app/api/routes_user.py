"""账号 / 行程收藏 / 地理定位 / 城市图片 接口。"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.services import auth as auth_svc
from app.services import orders as orders_svc
from app.services import photos as photo_svc
from app.services import poi as poi_svc
from app.services import poi_photos as poi_photo_svc
from app.services import transport as transport_svc

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- 鉴权
def _token(authorization: str) -> str:
    return (authorization or "").replace("Bearer ", "").strip()


def current_user(authorization: str = Header(default="")) -> dict[str, Any]:
    user = auth_svc.user_from_token(_token(authorization))
    if not user:
        raise HTTPException(401, "登录状态已失效，请重新登录")
    return user


def optional_user(authorization: str = Header(default="")) -> dict[str, Any] | None:
    return auth_svc.user_from_token(_token(authorization))


# ---------------------------------------------------------------- 配置
@router.get("/public-config")
async def public_config() -> dict[str, Any]:
    """前端启动时需要知道的开关，不含任何密钥。"""
    return {
        "allowed_email_domain": settings.allowed_email_domain,
        "mail_ready": settings.mail_ready,
        "photos_ready": settings.photos_ready,
        "photos": photo_svc.coverage(),
        "code_ttl": 300,
    }


# ---------------------------------------------------------------- 注册登录
class CodeReq(BaseModel):
    email: str


class RegisterReq(BaseModel):
    email: str
    password: str = Field(..., min_length=8, max_length=64)
    code: str
    city_id: str = ""
    nickname: str = ""


class LoginReq(BaseModel):
    email: str
    password: str


@router.post("/auth/code")
async def send_code(req: CodeReq) -> dict[str, Any]:
    return await auth_svc.issue_code(req.email, "register")


@router.post("/auth/register")
async def register(req: RegisterReq) -> dict[str, Any]:
    city = poi_svc.get_city(req.city_id) if req.city_id else None
    result = auth_svc.register(
        req.email, req.password, req.code,
        city_id=req.city_id, city_name=city["name"] if city else "",
        nickname=req.nickname.strip()[:20],
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("message", "注册失败"))
    return result


@router.post("/auth/login")
async def login(req: LoginReq) -> dict[str, Any]:
    result = auth_svc.login(req.email, req.password)
    if not result.get("ok"):
        raise HTTPException(400, result.get("message", "登录失败"))
    return result


@router.post("/auth/logout")
async def logout(authorization: str = Header(default="")) -> dict[str, Any]:
    auth_svc.logout(_token(authorization))
    return {"ok": True}


@router.get("/auth/me")
async def me(authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "未登录")
    return {"user": u}


class CityReq(BaseModel):
    city_id: str


@router.post("/auth/city")
async def update_city(req: CityReq, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "未登录")
    city = poi_svc.get_city(req.city_id)
    if not city:
        raise HTTPException(404, "城市未收录")
    return {"user": auth_svc.update_city(u["id"], city["id"], city["name"])}


# ---------------------------------------------------------------- 定位
def _dist_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * r * asin(sqrt(a)), 1)


@router.get("/geo/nearest")
async def nearest_city(lat: float = Query(...), lon: float = Query(...)) -> dict[str, Any]:
    """根据浏览器坐标推算最近的城市（本地算，不调外部逆地理编码）。"""
    cities = poi_svc.list_cities()
    scored = [(_dist_km(lat, lon, c["lat"], c["lon"]), c) for c in cities]
    scored.sort(key=lambda x: x[0])
    d, city = scored[0]
    return {"city": city, "distance_km": d,
            "nearby": [{"id": c["id"], "name": c["name"], "distance_km": dd}
                       for dd, c in scored[:5]]}


# ---------------------------------------------------------------- 图片
@router.get("/photos/{city_id}")
async def city_photos(city_id: str, force: bool = False) -> dict[str, Any]:
    if not poi_svc.get_city(city_id):
        raise HTTPException(404, "城市未收录")
    if not settings.photos_ready:
        return {"city_id": city_id, "enabled": False, "items": [],
                "hint": "未配置 UNSPLASH_ACCESS_KEY，前端使用渐变占位"}
    items = photo_svc.public_photos(city_id)
    if not items or force:
        await photo_svc.fetch_city_photos(city_id, force=force)
        items = photo_svc.public_photos(city_id)
    return {"city_id": city_id, "enabled": True, "items": items}


@router.get("/photos")
async def all_photos() -> dict[str, Any]:
    """一次性返回所有城市的图片，供首页/探索页批量渲染。"""
    data = {}
    for c in poi_svc.list_cities():
        items = photo_svc.public_photos(c["id"])
        if items:
            data[c["id"]] = items
    return {"enabled": settings.photos_ready, "cities": data, "coverage": photo_svc.coverage()}


# ---------------------------------------------------------------- 景点图片
@router.get("/pois/{city_id}/photos")
async def poi_photos(city_id: str, name: str, force: bool = False) -> dict[str, Any]:
    """某个景点自己的实拍照片（按需拉取并落地缓存）。"""
    if not poi_svc.get_city(city_id):
        raise HTTPException(404, "城市未收录")
    if not poi_svc.get_pois(city_id):
        raise HTTPException(404, "该城市没有景点数据")
    if not settings.photos_ready:
        return {"city_id": city_id, "poi": name, "enabled": False, "items": [],
                "hint": "未配置 UNSPLASH_ACCESS_KEY"}
    items = poi_photo_svc.public_poi_photos(city_id, name)
    if not items and not force:
        rl = poi_photo_svc.rate_limit_state()
        if rl["limited"]:
            return {"city_id": city_id, "poi": name, "enabled": True, "items": [],
                    "rate_limited": True, "retry_in_min": rl["retry_in_min"],
                    "hint": f"图片接口限流中，约 {rl['retry_in_min']} 分钟后可再试"}
        await poi_photo_svc.fetch_poi_photos(city_id, name)
        items = poi_photo_svc.public_poi_photos(city_id, name)
    elif force:
        await poi_photo_svc.fetch_poi_photos(city_id, name, force=True)
        items = poi_photo_svc.public_poi_photos(city_id, name)
    return {"city_id": city_id, "poi": name, "enabled": True, "items": items,
            "rate_limited": poi_photo_svc.rate_limit_state()["limited"]}


@router.get("/poi-photos/coverage")
async def poi_photo_coverage() -> dict[str, Any]:
    return poi_photo_svc.poi_photo_stats()


@router.get("/cities/{city_id}/poi-photos")
async def city_poi_photo_manifest(city_id: str) -> dict[str, Any]:
    """该城哪些景点已经有实景照片（前端用来标「有图」）。"""
    if not poi_svc.get_city(city_id):
        raise HTTPException(404, "城市未收录")
    m = poi_photo_svc.load_manifest(city_id)
    return {"city_id": city_id,
            "with_photo": sorted(m.keys()),
            "count": len(m),
            "rate_limited": poi_photo_svc.rate_limit_state()["limited"]}


# ---------------------------------------------------------------- 交通与住宿
@router.get("/transport/train")
async def train_query(origin: str, destination: str, travel_date: str = "",
                      people: int = 1) -> dict[str, Any]:
    """两城之间的城际交通方案（按距离推算的参考区间 + 官方/OTA 链接）。"""
    return transport_svc.query_trains(origin, destination, travel_date, people)


@router.get("/transport/hotel")
async def hotel_query(city: str, near_poi: str = "", people: int = 2,
                      nights: int = 2, level: str = "中等") -> dict[str, Any]:
    """住宿区域建议与价位区间（基于景点分布推算 + OTA 链接）。"""
    return transport_svc.query_hotels(city, near_poi, people, nights, level)


# ---------------------------------------------------------------- 我的行程
class SavePlanReq(BaseModel):
    payload: dict[str, Any]


@router.post("/plans")
async def save_plan(req: SavePlanReq, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录再收藏行程")
    pid = auth_svc.save_plan(u["id"], req.payload)
    return {"ok": True, "id": pid}


@router.get("/plans")
async def list_plans(authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    return {"items": auth_svc.list_plans(u["id"])}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    row = auth_svc.get_plan(u["id"], plan_id)
    if not row:
        raise HTTPException(404, "行程不存在")
    return row


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    if not auth_svc.delete_plan(u["id"], plan_id):
        raise HTTPException(404, "行程不存在")
    return {"ok": True}


# ---------------------------------------------------------------- 分享
@router.post("/plans/{plan_id}/share")
async def share_plan(plan_id: str, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    token = auth_svc.share_plan(u["id"], plan_id)
    if not token:
        raise HTTPException(404, "行程不存在")
    return {"ok": True, "token": token, "path": f"/s/{token}"}


@router.delete("/plans/{plan_id}/share")
async def unshare_plan(plan_id: str, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    if not auth_svc.unshare_plan(u["id"], plan_id):
        raise HTTPException(404, "行程不存在")
    return {"ok": True}


@router.get("/share/{token}")
async def get_shared(token: str) -> dict[str, Any]:
    """公开只读接口，不需要登录。"""
    row = auth_svc.get_shared(token)
    if not row:
        raise HTTPException(404, "分享链接不存在或已取消分享")
    return {"title": row["title"], "city": row["city"], "days": row["days"],
            "author": row.get("nickname") or "云游用户",
            "created_at": row["created_at"], "payload": row["payload"]}


# ---------------------------------------------------------------- 重置密码
class ResetCodeReq(BaseModel):
    email: str


class ResetReq(BaseModel):
    email: str
    code: str
    password: str = Field(..., min_length=8, max_length=64)


@router.post("/auth/reset-code")
async def reset_code(req: ResetCodeReq) -> dict[str, Any]:
    return await auth_svc.issue_code(req.email, "reset")


@router.post("/auth/reset")
async def reset_password(req: ResetReq) -> dict[str, Any]:
    result = auth_svc.reset_password(req.email, req.code, req.password)
    if not result.get("ok"):
        raise HTTPException(400, result.get("message", "重置失败"))
    return result


# ---------------------------------------------------------------- 订单
class OrderReq(BaseModel):
    type: str = "ticket"
    title: str = Field(..., min_length=1, max_length=80)
    city: str = ""
    detail: str = ""
    amount: float = 0
    quantity: int = 1
    travel_date: str = ""
    status: str = "pending"
    note: str = ""


class OrderStatusReq(BaseModel):
    status: str


class OrderImportReq(BaseModel):
    payload: dict[str, Any]
    plan_id: str = ""


@router.get("/orders/summary")
async def orders_summary(authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    return orders_svc.summary(u["id"])


@router.get("/orders")
async def list_orders(type: str = "", authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    return {"items": orders_svc.list_orders(u["id"], type),
            "summary": orders_svc.summary(u["id"])}


@router.post("/orders")
async def create_order(req: OrderReq, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    oid = orders_svc.create(u["id"], req.model_dump())
    return {"ok": True, "id": oid}


@router.patch("/orders/{order_id}")
async def update_order(order_id: str, req: OrderStatusReq,
                       authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    if not orders_svc.update_status(u["id"], order_id, req.status):
        raise HTTPException(404, "订单不存在")
    return {"ok": True}


@router.delete("/orders/{order_id}")
async def delete_order(order_id: str, authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录")
    if not orders_svc.delete(u["id"], order_id):
        raise HTTPException(404, "订单不存在")
    return {"ok": True}


@router.post("/orders/import")
async def import_orders(req: OrderImportReq,
                        authorization: str = Header(default="")) -> dict[str, Any]:
    u = auth_svc.user_from_token(_token(authorization))
    if not u:
        raise HTTPException(401, "请先登录再生成订单")
    result = orders_svc.import_from_plan(u["id"], req.payload, req.plan_id)
    if not result.get("ok"):
        raise HTTPException(400, result.get("message", "生成失败"))
    return result
