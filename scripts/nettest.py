"""探测图片源与外部接口连通性。"""
import io

import httpx

OUT = io.open(r"D:\shot_tmp\nettest.txt", "w", encoding="utf-8", buffering=1)

TARGETS = [
    ("wikipedia_api", "https://zh.wikipedia.org/api/rest_v1/page/summary/" + httpx.URL("").copy_with(path="/贵阳").path),
    ("wikipedia_main", "https://zh.wikipedia.org/w/api.php?action=query&titles=%E8%B4%B5%E9%98%B3&prop=pageimages&format=json&pithumbsize=800"),
    ("wikimedia_cdn", "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Jiaxiu_Pavilion.jpg/640px-Jiaxiu_Pavilion.jpg"),
    ("unsplash_cdn", "https://images.unsplash.com/photo-1508804185872-d7badad00f7d?w=400"),
    ("pexels_cdn", "https://images.pexels.com/photos/2412603/pexels-photo-2412603.jpeg?w=400"),
    ("open_meteo", "https://api.open-meteo.com/v1/forecast?latitude=26.6&longitude=106.6&current=temperature_2m"),
]

with httpx.Client(timeout=15, follow_redirects=True) as c:
    for name, url in TARGETS:
        try:
            r = c.get(url, headers={"User-Agent": "wenlv-assistant/1.0"})
            print(f"{name:16} {r.status_code}  len={len(r.content):>8}  ct={r.headers.get('content-type','')[:40]}", file=OUT)
        except Exception as e:
            print(f"{name:16} FAIL  {type(e).__name__}: {str(e)[:70]}", file=OUT)

OUT.close()
