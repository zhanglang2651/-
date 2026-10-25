"""文旅助手 · FastAPI 应用入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.api.routes_user import router as user_router
from app.config import settings
from app.services import db as db_svc
from app.services import photos as photo_svc
from app.services import poi as poi_svc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wenlv")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_svc.init_db()
    cities = poi_svc.list_cities()
    total = sum(len(poi_svc.get_pois(c["id"])) for c in cities)
    log.info("知识库加载完成：%d 城 / %d 个景点", len(cities), total)
    log.info("LLM 网关：%s | 模型：%s", settings.base_url, settings.model)
    if not settings.llm_ready:
        log.warning("未检测到有效 API Key，AI 能力将降级为规则模式")
    cov = photo_svc.coverage()
    log.info("城市图片：%d 城 / %d 张（Unsplash %s）", cov["cities"], cov["photos"],
             "已配置" if settings.photos_ready else "未配置，使用渐变占位")
    log.info("邮件服务：%s", "已配置" if settings.mail_ready else "未配置，验证码走开发模式")
    yield
    log.info("服务关闭")


app = FastAPI(title="云游 · 文旅智能助手", version="1.0.0",
              description="AI 行程规划 + 城市旅游热点实时推送", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(user_router)
app.mount("/static", StaticFiles(directory=str(settings.web_dir)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(settings.web_dir / "index.html"))


@app.get("/s/{token}")
async def share_page(token: str) -> FileResponse:
    """行程分享只读页（无需登录）。"""
    return FileResponse(str(settings.web_dir / "share.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
