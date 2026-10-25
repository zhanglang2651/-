"""探测：景点级图片源可用性。测 Unsplash 与 Wikimedia Commons 对中文景点名的覆盖。"""
from __future__ import annotations

import asyncio
import io
import sys

import httpx

sys.path.insert(0, r"D:\文旅助手")
from app.config import settings  # noqa: E402

OUT = io.open(r"D:\shot_tmp\poi_img_probe.txt", "w", encoding="utf-8", buffering=1)
UA = "wenlv-assistant/1.0 (wenlv@example.com)"

# 测试用景点名（中文）与可能对应的英文检索词
CASES = [
    ("甲秀楼", "Guiyang", "Jiaxiu Pavilion"),
    ("黄果树瀑布", "Anshun", "Huangguoshu Waterfall"),
    ("大熊猫繁育研究基地", "Chengdu", "giant panda breeding base chengdu"),
    ("兵马俑", "Xian", "Terracotta Army"),
    ("漓江竹筏", "Guilin", "Li River bamboo raft"),
]

WIKI = "https://commons.wikimedia.org/w/api.php"
UNS = "https://api.unsplash.com/search/photos"


async def wiki(client, q, n=3):
    r = await client.get(WIKI, params={
        "action": "query", "generator": "search", "gsrsearch": q,
        "gsrnamespace": "6", "gsrlimit": n,
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": "1600", "format": "json",
    })
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        thumb = ii.get("thumburl") or ii.get("url")
        if thumb:
            out.append((p.get("title", "")[:60], thumb[:110]))
    return out


async def unsplash(client, q, n=3):
    r = await client.get(UNS, params={
        "query": q, "per_page": n, "orientation": "landscape",
        "client_id": settings.unsplash_key,
    })
    r.raise_for_status()
    return [(it.get("id", "")[:12], (it.get("alt_description") or "")[:50])
            for it in r.json().get("results", [])]


async def main():
    async with httpx.AsyncClient(timeout=25, headers={"User-Agent": UA}) as c:
        print("=== 连通性 ===", file=OUT)
        for name, url in [("commons-api", WIKI),
                          ("commons-cdn", "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Jiaxiu_Pavilion.jpg/640px-Jiaxiu_Pavilion.jpg"),
                          ("unsplash-api", UNS)]:
            try:
                r = await c.get(url)
                print(f"  {name}: {r.status_code} len={len(r.content)}", file=OUT)
            except Exception as e:
                print(f"  {name}: FAIL {type(e).__name__} {str(e)[:80]}", file=OUT)

        print("\n=== 中文景点名搜索 ===", file=OUT)
        for cn, city, en in CASES:
            try:
                res = await wiki(c, cn)
                print(f"  [Commons] {cn}: {len(res)} 条", file=OUT)
                for t, u in res[:2]:
                    print(f"      {t} | {u}", file=OUT)
            except Exception as e:
                print(f"  [Commons] {cn}: FAIL {str(e)[:70]}", file=OUT)
            await asyncio.sleep(0.6)

        print("\n=== 英文检索词搜索（Unsplash） ===", file=OUT)
        for cn, city, en in CASES:
            try:
                res = await unsplash(c, en)
                print(f"  [Unsplash] {en}: {len(res)} 条 -> {res}", file=OUT)
            except Exception as e:
                print(f"  [Unsplash] {en}: FAIL {str(e)[:70]}", file=OUT)
            await asyncio.sleep(0.4)


asyncio.run(main())
OUT.close()
