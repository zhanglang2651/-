"""景点级图片服务。

与城市级图片（services/photos.py）的区别：
- 城市级：按城市英文检索词，取「城市氛围照」
- 景点级：按**单个景点**的英文检索词（app/data/poi_queries.json，由 LLM 离线生成），
  取该景点本身的实拍照片

存储：web/assets/poi_photos/<city_id>/<poi序号>.jpg + manifest.json
策略：
- 检索词由 LLM 离线生成并落盘，运行期只查 Unsplash
- Unsplash 免费档 50 次/小时，所以：一次查询多取几张 → 本地缓存 → 之后直接读盘
- 没配 key 或搜不到时返回空列表，前端降级为城市照 / 无图占位
"""
from __future__ import annotations

import asyncio
import io
import json
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.services import poi as poi_svc

API = "https://api.unsplash.com/search/photos"
UA = "wenlv-assistant/1.0 (wenlv@example.com)"
QUERIES_FILE = settings.data_dir / "poi_queries.json"
PER_POI = 3


def _queries() -> dict[str, dict[str, list[str]]]:
    if not QUERIES_FILE.exists():
        return {}
    try:
        return json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _slug(name: str) -> str:
    """把中文景点名转成安全的文件标识（保留可读性，用序号更稳）。"""
    import hashlib
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:10]


def _dir(city_id: str):
    return settings.photo_dir.parent / "poi_photos" / city_id


def _manifest_path(city_id: str):
    return _dir(city_id) / "manifest.json"


def load_manifest(city_id: str) -> dict[str, list[dict[str, Any]]]:
    """{景点名: [图片条目]}"""
    p = _manifest_path(city_id)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        out: dict[str, list[dict[str, Any]]] = {}
        for name, items in data.items():
            ok = []
            for it in items:
                f = _dir(city_id) / it["file"]
                if f.exists() and f.stat().st_size > 2000:
                    ok.append(it)
            if ok:
                out[name] = ok
        return out
    except Exception:  # noqa: BLE001
        return {}


def _save_manifest(city_id: str, data: dict[str, list[dict[str, Any]]]) -> None:
    d = _dir(city_id)
    d.mkdir(parents=True, exist_ok=True)
    _manifest_path(city_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def _search(client: httpx.AsyncClient, query: str, count: int) -> list[dict[str, Any]]:
    r = await client.get(API, params={
        "query": query, "per_page": count, "orientation": "landscape",
        "client_id": settings.unsplash_key,
    })
    r.raise_for_status()
    out = []
    for item in r.json().get("results", []):
        out.append({
            "id": item["id"],
            "url": item["urls"]["regular"] + "&w=1400&q=80&fm=jpg",
            "thumb": item["urls"]["small"] + "&w=400&q=70&fm=jpg",
            "author": (item.get("user") or {}).get("name") or "Unsplash",
            "link": (item.get("links") or {}).get("html") or "https://unsplash.com",
            "desc": (item.get("alt_description") or item.get("description") or "").strip()[:120],
            "query": query,
        })
    return out


async def fetch_poi_photos(city_id: str, poi_name: str,
                           force: bool = False) -> list[dict[str, Any]]:
    """取某景点的图片：先读本地缓存，没有就查 Unsplash 并落地。

    Unsplash 免费档每小时只允许 50 次搜索请求，所以：
    - 命中缓存直接返回，不打上游
    - 未命中才请求，一次查 2 个检索词拿多张
    - 被限流（403/429）时返回空并附带原因，让前端如实告知用户
    """
    manifest = load_manifest(city_id)
    cached = manifest.get(poi_name, [])
    if cached and not force:
        return cached
    if not settings.photos_ready:
        return []

    qmap = _queries().get(city_id, {})
    queries = qmap.get(poi_name) or []
    if not queries:
        return cached

    d = _dir(city_id)
    d.mkdir(parents=True, exist_ok=True)
    picked: list[dict[str, Any]] = []
    rate_limited = False
    try:
        async with httpx.AsyncClient(timeout=25, headers={"User-Agent": UA}) as client:
            seen: set[str] = set()
            for q in queries:
                if len(picked) >= PER_POI:
                    break
                try:
                    batch = await _search(client, q, 2)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (403, 429):
                        rate_limited = True
                        break
                    continue
                except Exception:  # noqa: BLE001
                    continue
                for item in batch:
                    if item["id"] in seen:
                        continue
                    seen.add(item["id"])
                    picked.append(item)
                    if len(picked) >= PER_POI:
                        break
                await asyncio.sleep(0.2)

            if rate_limited and not picked:
                _set_rate_limit()
                return cached

            saved: list[dict[str, Any]] = []
            for i, item in enumerate(picked[:PER_POI], 1):
                fname = f"{_slug(poi_name)}_{i}.jpg"
                try:
                    resp = await client.get(item["url"])
                    resp.raise_for_status()
                    if len(resp.content) < 5000:
                        continue
                    (d / fname).write_bytes(resp.content)
                    saved.append({"file": fname, "author": item["author"],
                                  "link": item["link"], "desc": item["desc"],
                                  "query": item["query"]})
                except Exception:  # noqa: BLE001
                    continue
            if saved:
                manifest[poi_name] = saved
                _save_manifest(city_id, manifest)
                return saved
    except Exception:  # noqa: BLE001
        return cached
    return cached


# ---------------------------------------------------------------- 限流状态
_RATE_LIMIT_FILE = settings.photo_dir.parent / "poi_photos" / ".rate_limited"


def _set_rate_limit() -> None:
    """记录限流发生时间（用于前端提示何时可再试）。"""
    try:
        _RATE_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _RATE_LIMIT_FILE.write_text(datetime.now().isoformat(timespec="seconds"),
                                     encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def rate_limit_state() -> dict[str, Any]:
    """当前是否处于限流冷却期，以及剩余分钟数。"""
    if not _RATE_LIMIT_FILE.exists():
        return {"limited": False, "retry_in_min": 0}
    try:
        ts = datetime.strptime(_RATE_LIMIT_FILE.read_text(encoding="utf-8"),
                                "%Y-%m-%dT%H:%M:%S")
    except Exception:  # noqa: BLE001
        return {"limited": False, "retry_in_min": 0}
    # Unsplash 免费档按小时重置，用 55 分钟作为保守冷却
    waited = (datetime.now() - ts).total_seconds() / 60
    remain = max(0, 55 - waited)
    return {"limited": remain > 0, "retry_in_min": int(remain) + 1}


def public_poi_photos(city_id: str, poi_name: str) -> list[dict[str, Any]]:
    """给前端的结构：本地 URL + 缩略图 + 署名 + 图片描述。"""
    items = load_manifest(city_id).get(poi_name, [])
    out = []
    for it in items:
        out.append({
            "url": f"/static/assets/poi_photos/{city_id}/{it['file']}",
            "author": it.get("author", "Unsplash"),
            "link": it.get("link", "https://unsplash.com"),
            "desc": it.get("desc", ""),
            "query": it.get("query", ""),
        })
    return out


def poi_photo_stats() -> dict[str, Any]:
    """已落地景点图片的统计。"""
    total, cities = 0, {}
    base = settings.photo_dir.parent / "poi_photos"
    if base.exists():
        for d in base.iterdir():
            if not d.is_dir():
                continue
            m = load_manifest(d.name)
            if m:
                cities[d.name] = sum(len(v) for v in m.values())
                total += cities[d.name]
    return {"cities": len(cities), "pois": sum(1 for _ in []), "photos": total,
            "per_city": cities}


def pois_without_photos(city_id: str) -> list[str]:
    """该城还没有图片的景点名。"""
    manifest = load_manifest(city_id)
    return [p["name"] for p in poi_svc.get_pois(city_id) if not manifest.get(p["name"])]
