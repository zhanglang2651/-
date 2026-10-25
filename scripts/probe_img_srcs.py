"""探测：有没有本机可达、且覆盖中国景点实拍的图片源。"""
from __future__ import annotations

import asyncio
import io

import httpx

OUT = io.open(r"D:\shot_tmp\img_src_probe.txt", "w", encoding="utf-8", buffering=1)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) wenlv-assistant/1.0"

HOSTS = [
    ("wikimedia-b", "https://commons.wikimedia.org/wiki/Special:FilePath/Jiaxiu_Pavilion.jpg?width=800"),
    ("wm-mirror-1", "https://upload.wikimedia.beta.wmcloud.org/wikipedia/commons/thumb/e/e0/Jiaxiu_Pavilion.jpg/640px-Jiaxiu_Pavilion.jpg"),
    ("wikidata", "https://www.wikidata.org/w/api.php?action=query&format=json&titles=Q1"),
    ("baike", "https://baike.baidu.com/item/%E7%94%B2%E7%A7%80%E6%A5%BC"),
    ("pexels-cdn", "https://images.pexels.com/photos/1534560/pexels-photo-1534560.jpeg?auto=compress&w=400"),
    ("pexels-api", "https://api.pexels.com/v1/search?query=panda&per_page=1"),
    ("pixabay-cdn", "https://cdn.pixabay.com/photo/2016/11/29/05/45/astronomy-1867616_960_720.jpg"),
    ("openverse", "https://api.openverse.org/v1/images/?q=jiaxiu%20pavilion&page_size=3"),
    ("loc-gov-cn", "http://www.ncha.gov.cn/"),
    ("trip-static", "https://you.ctrip.com/"),
    ("qunar", "https://www.qunar.com/"),
]


async def probe(c, name, url):
    try:
        r = await c.get(url, timeout=18)
        ct = (r.headers.get("content-type") or "")[:40]
        print(f"{name:16s} {r.status_code:4d} len={len(r.content):8d} {ct}", file=OUT)
        return r
    except Exception as e:
        print(f"{name:16s} FAIL {type(e).__name__}: {str(e)[:60]}", file=OUT)
        return None


async def main():
    async with httpx.AsyncClient(timeout=18, headers={"User-Agent": UA},
                                 follow_redirects=True) as c:
        for name, url in HOSTS:
            await probe(c, name, url)
            await asyncio.sleep(0.3)


asyncio.run(main())
OUT.close()
