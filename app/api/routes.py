"""HTTP 接口层：REST + SSE 流式推送。"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.chat_agent import stream_chat
from app.agents.graph import run_plan
from app.agents.revise import revise_day
from app.config import settings
from app.services import auth as auth_svc
from app.services import poi as poi_svc
from app.services import seasonal as season_svc
from app.services import trends as trend_svc
from app.services import weather as weather_svc
from app.services.cache import cache
from app.services.ratelimit import (LLM_PER_IP, PLAN_PER_USER, PLAN_WINDOW, REVISE_PER_USER,
                                    limiter)

router = APIRouter(prefix="/api")

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown"))


def _guard_ai(user: dict[str, Any], request: Request) -> None:
    """AI 接口双层限流：按 IP 兜底，按用户配额卡住主力消耗。"""
    ip = _client_ip(request)
    ok, wait = limiter.allow(f"ai:ip:{ip}", LLM_PER_IP, 3600)
    if not ok:
        raise HTTPException(429, f"请求过于频繁，请 {max(1, wait // 60)} 分钟后再试")


# ------------------------------------------------------------------ meta
@router.get("/health")
async def health() -> dict[str, Any]:
    from app.core.resilience import stats

    return {
        "status": "ok",
        "llm_ready": settings.llm_ready,
        "model": settings.model,
        "model_fast": settings.model_fast,
        "cities": len(poi_svc.list_cities()),
        "pois": sum(len(poi_svc.get_pois(c["id"])) for c in poi_svc.list_cities()),
        "usage": stats.snapshot(),
        "time": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/usage")
async def usage() -> dict[str, Any]:
    """今日模型调用与 token 消耗，用于成本观测。"""
    from app.core.resilience import stats

    snap = stats.snapshot()
    snap["quota"] = {"plan_per_user": PLAN_PER_USER, "llm_per_ip": LLM_PER_IP}
    return snap


@router.get("/cities")
async def cities() -> dict[str, Any]:
    return {"count": len(poi_svc.list_cities()), "items": poi_svc.list_cities()}


@router.get("/cities/{city_id}/pois")
async def city_pois(city_id: str) -> dict[str, Any]:
    city = poi_svc.get_city(city_id)
    if not city:
        raise HTTPException(404, "城市未收录")
    return {"city": city, "items": poi_svc.get_pois(city_id)}


@router.get("/search")
async def search(q: str = Query(..., min_length=1)) -> dict[str, Any]:
    return {"keyword": q, "items": poi_svc.search(q)}


# ------------------------------------------------------------------ 时令与玩法
@router.get("/season")
async def season() -> dict[str, Any]:
    """当前节气、应季城市、节庆与玩法主题。"""
    return {
        "term": season_svc.current_term(),
        "best_cities": season_svc.best_cities_now(),
        "festivals": season_svc.festivals_now(),
        "themes": season_svc.theme_overview(),
        "foods": season_svc.food_cities(),
        "routes": season_svc.routes_now(),
        "matrix": season_svc.season_matrix(),
    }


@router.get("/season/matrix")
async def season_matrix() -> dict[str, Any]:
    return season_svc.season_matrix()


@router.get("/themes")
async def themes() -> dict[str, Any]:
    return {"items": season_svc.theme_overview()}


# ------------------------------------------------------------------ weather
@router.get("/weather/{city_id}")
async def weather(city_id: str) -> dict[str, Any]:
    city = poi_svc.get_city(city_id)
    if not city:
        raise HTTPException(404, "城市未收录")
    return await weather_svc.fetch_weather(city["lat"], city["lon"], 7)


# ------------------------------------------------------------------ trends
@router.get("/trends/overview")
async def overview(limit: int = 8) -> dict[str, Any]:
    rows = await cache.get_or_set(
        f"overview:{limit}", 120, lambda: trend_svc.multi_city_ranking(limit)
    )
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "items": rows}


@router.get("/trends/{city_id}")
async def trends(city_id: str, tick: int = 0) -> dict[str, Any]:
    try:
        return await trend_svc.city_trends(city_id, tick=tick)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/trends/{city_id}/stream")
async def trends_stream(city_id: str, times: int = 90) -> StreamingResponse:
    """热点实时推送：先推全量快照，之后每 20 秒推一次增量。"""
    if not poi_svc.get_city(city_id):
        raise HTTPException(404, "城市未收录")

    async def gen() -> AsyncGenerator[str, None]:
        tick = 0
        try:
            while tick < times:
                data = await trend_svc.city_trends(city_id, tick=tick, with_ai=(tick == 0))
                yield sse("snapshot" if tick == 0 else "update", data)
                tick += 1
                await asyncio.sleep(20)
        except asyncio.CancelledError:
            return

    return StreamingResponse(gen(), media_type="text/event-stream; charset=utf-8",
                             headers=SSE_HEADERS)


# ------------------------------------------------------------------ plan
class PlanReq(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    origin: str = ""


@router.post("/plan")
async def plan(req: PlanReq, request: Request,
               authorization: str = Header(default="")) -> StreamingResponse:
    # 行程规划消耗大模型额度，要求登录 + 配额
    user = auth_svc.user_from_token((authorization or "").replace("Bearer ", "").strip())
    if not user:
        raise HTTPException(401, "生成行程需要先登录（浏览与热点无需登录）")
    _guard_ai(user, request)
    ok, wait = limiter.allow(f"plan:u:{user['id']}", PLAN_PER_USER, PLAN_WINDOW)
    if not ok:
        raise HTTPException(429, f"每小时最多生成 {PLAN_PER_USER} 次行程，请 {max(1, wait // 60)} 分钟后再试")

    async def gen() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        emit = lambda evt: queue.put_nowait(evt)  # noqa: E731
        task = asyncio.create_task(run_plan(req.query, emit, origin=req.origin))
        try:
            while True:
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=0.4)
                    yield sse("step", evt)
                except asyncio.TimeoutError:
                    if task.done():
                        break
                    yield ": keep-alive\n\n"
            result = await task
            yield sse("plan", result)
            yield sse("done", {"ok": result.get("ok", False)})
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as exc:  # noqa: BLE001
            yield sse("error", {"message": f"规划失败：{exc}"})

    return StreamingResponse(gen(), media_type="text/event-stream; charset=utf-8",
                             headers=SSE_HEADERS)


# ------------------------------------------------------------------ revise
class ReviseReq(BaseModel):
    plan: dict[str, Any]
    day: int = Field(..., ge=1, le=10)
    instruction: str = Field("", max_length=200)


@router.post("/plan/revise")
async def revise(req: ReviseReq, request: Request,
                 authorization: str = Header(default="")) -> dict[str, Any]:
    """只重排行程中的某一天，避免整条链路重跑。"""
    user = auth_svc.user_from_token((authorization or "").replace("Bearer ", "").strip())
    if not user:
        raise HTTPException(401, "修改行程需要先登录")
    _guard_ai(user, request)
    ok, wait = limiter.allow(f"revise:u:{user['id']}", REVISE_PER_USER, 3600)
    if not ok:
        raise HTTPException(429, f"修改太频繁，请 {max(1, wait // 60)} 分钟后再试")
    try:
        new_plan = await revise_day(req.plan, req.day, req.instruction)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"修改失败：{exc}") from exc
    return {"ok": True, "plan": new_plan, "day": req.day}


# ------------------------------------------------------------------ chat
class ChatReq(BaseModel):
    messages: list[dict[str, str]] = Field(..., min_length=1)


@router.post("/chat")
async def chat(req: ChatReq, request: Request) -> StreamingResponse:
    _guard_ai({}, request)

    async def gen() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        emit = lambda evt: queue.put_nowait(evt)  # noqa: E731
        task = asyncio.create_task(stream_chat(req.messages, emit))
        try:
            while True:
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=0.4)
                    yield sse(evt.get("type", "message"), evt)
                except asyncio.TimeoutError:
                    if task.done():
                        break
                    yield ": keep-alive\n\n"
            answer = await task
            yield sse("done", {"answer": answer})
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as exc:  # noqa: BLE001
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream; charset=utf-8",
                             headers=SSE_HEADERS)
