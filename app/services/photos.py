"""城市真实图片服务（Unsplash）。

策略：
- 按城市的英文检索词搜 Unsplash，取横图，下载到 web/assets/photos/<city>/
- 落地 manifest.json，之后直接读本地文件，不再打上游
- 没配 UNSPLASH_ACCESS_KEY 时返回空列表，前端自动降级为渐变占位
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import httpx

from app.config import settings

API = "https://api.unsplash.com/search/photos"
# Wikimedia Commons 作为免费补充数据源：无需 API Key，中国景点实景覆盖好。
# 注意：需带 User-Agent，且请求间应留间隔，避免 429 限流。
WIKI_API = "https://commons.wikimedia.org/w/api.php"
UA = "wenlv-assistant/1.0 (wenlv@example.com)"
QUERIES_FILE = settings.data_dir / "photo_queries.json"
PER_CITY = 3


def _queries() -> dict[str, list[str]]:
    return json.loads(QUERIES_FILE.read_text(encoding="utf-8"))


def _manifest_path(city_id: str):
    return settings.photo_dir / city_id / "manifest.json"


def load_manifest(city_id: str) -> list[dict[str, Any]]:
    p = _manifest_path(city_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # 校验文件还在
        ok = []
        for item in data:
            f = settings.photo_dir / city_id / item["file"]
            if f.exists() and f.stat().st_size > 2000:
                ok.append(item)
        return ok
    except Exception:  # noqa: BLE001
        return []


async def _search(client: httpx.AsyncClient, query: str, count: int) -> list[dict[str, Any]]:
    r = await client.get(API, params={
        "query": query, "per_page": count, "orientation": "landscape",
        "client_id": settings.unsplash_key,
    })
    r.raise_for_status()
    data = r.json()
    out = []
    for item in data.get("results", []):
        out.append({
            "id": item["id"],
            "url": item["urls"]["regular"] + "&w=1000&q=75&fm=jpg",
            "author": (item.get("user") or {}).get("name") or "Unsplash",
            "link": (item.get("links") or {}).get("html") or "https://unsplash.com",
            "query": query,
        })
    return out


async def _wikicommons_search(client: httpx.AsyncClient, query: str, count: int) -> list[dict[str, Any]]:
    """在 Wikimedia Commons 搜索图片，返回与 Unsplash 相同结构的条目。

    返回的 url 是 thumburl（iiurlwidth=1600 的缩略图），author 取自摄影师信息。
    """
    r = await client.get(WIKI_API, params={
        "action": "query", "generator": "search", "gsrsearch": query,
        "gsrnamespace": "6", "gsrlimit": count,
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": "1600", "format": "json",
    })
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    out = []
    for page in pages.values():
        ii = (page.get("imageinfo") or [{}])[0]
        thumb = ii.get("thumburl") or ii.get("url")
        if not thumb:
            continue
        author = "Wikimedia"
        try:
            artist = ii.get("extmetadata", {}).get("Artist", {}).get("value", "")
            # Wikimedia 的 Artist 常为 HTML，去掉标签再截断
            import re as _re
            artist = _re.sub(r"<[^>]+>", " ", artist or "")
            artist = _re.sub(r"\s+", " ", artist).strip()
            author = artist[:40] or "Wikimedia"
        except Exception:  # noqa: BLE001
            pass
        out.append({
            "id": f"wm-{page.get('pageid', 'x')}",
            "url": thumb,
            "author": author,
            "link": ii.get("descriptionurl") or "https://commons.wikimedia.org",
            "query": query,
        })
    return out


async def fetch_city_photos(city_id: str, force: bool = False) -> list[dict[str, Any]]:
    """拉取并落地某城市的照片，返回 manifest。

    数据源顺序：优先 Unsplash；不足 PER_CITY 时用 Wikimedia Commons 补齐。
    已在本地缓存的照片会保留，不会因补拉被覆盖。
    """
    if not settings.photos_ready:
        return []
    existing = [] if force else load_manifest(city_id)
    if len(existing) >= PER_CITY:
        return existing

    queries = _queries().get(city_id, [])
    if not queries:
        return existing

    city_dir = settings.photo_dir / city_id
    city_dir.mkdir(parents=True, exist_ok=True)

    need = PER_CITY - len(existing)
    picked: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=25, headers={"User-Agent": UA}) as client:
            seen: set[str] = set()
            # 1) 优先 Unsplash（串行，避免免费应用 50 次/小时限流）
            for q in queries[:2]:
                try:
                    batch = await _search(client, q, 2)
                except Exception:  # noqa: BLE001
                    continue
                for item in batch:
                    if item["id"] in seen:
                        continue
                    seen.add(item["id"])
                    picked.append(item)
                    if len(picked) >= need:
                        break
                if len(picked) >= need:
                    break
                await asyncio.sleep(0.25)

            # 2) 不足则用 Wikimedia Commons 补齐（请求间隔 1s，礼貌限流）
            if len(picked) < need:
                for q in queries:
                    if len(picked) >= need:
                        break
                    try:
                        batch = await _wikicommons_search(client, q, need - len(picked) + 2)
                    except Exception:  # noqa: BLE001
                        continue
                    for item in batch:
                        if item["id"] in seen:
                            continue
                        seen.add(item["id"])
                        picked.append(item)
                        if len(picked) >= need:
                            break
                    await asyncio.sleep(1.0)

            # 下载新增图片（文件名延续现有编号，避免覆盖）
            saved = list(existing)
            used = {int(m["file"].split(".")[0]) for m in existing if m["file"].split(".")[0].isdigit()}
            next_no = 1
            while next_no in used:
                next_no += 1
            for item in picked:
                if len(saved) >= PER_CITY:
                    break
                try:
                    resp = await client.get(item["url"])
                    resp.raise_for_status()
                    if len(resp.content) < 5000:
                        continue
                    fname = f"{next_no}.jpg"
                    (city_dir / fname).write_bytes(resp.content)
                    saved.append({"file": fname, "author": item["author"],
                                  "link": item["link"], "query": item["query"]})
                    next_no += 1
                except Exception:  # noqa: BLE001
                    continue

            if saved:
                _manifest_path(city_id).write_text(
                    json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
                return saved
    except Exception:  # noqa: BLE001
        return load_manifest(city_id)
    return load_manifest(city_id)


def public_photos(city_id: str) -> list[dict[str, Any]]:
    """给前端的结构：本地 URL + 摄影师署名。"""
    items = load_manifest(city_id)
    out = []
    for it in items:
        out.append({
            "url": f"/static/assets/photos/{city_id}/{it['file']}",
            "author": it.get("author", "Unsplash"),
            "link": it.get("link", "https://unsplash.com"),
        })
    return out


def coverage() -> dict[str, Any]:
    """已落地图片的城市统计，用于前端提示。"""
    total, cities = 0, []
    if settings.photo_dir.exists():
        for d in settings.photo_dir.iterdir():
            if d.is_dir():
                n = len(load_manifest(d.name))
                if n:
                    cities.append(d.name)
                    total += n
    return {"cities": len(cities), "photos": total, "enabled": settings.photos_ready,
            "updated_at": datetime.now().isoformat(timespec="seconds")}
