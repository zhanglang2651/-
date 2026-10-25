"""探测：当前城市数据量 + 中国省级 GeoJSON 可用性。"""
import io
import json

import httpx

OUT = io.open(r"D:\shot_tmp\probe.txt", "w", encoding="utf-8", buffering=1)

cities = json.loads(open(r"D:\文旅助手\app\data\cities.json", encoding="utf-8").read())
pois = json.loads(open(r"D:\文旅助手\app\data\pois.json", encoding="utf-8").read())
print(f"cities={len(cities)}  pois={sum(len(v) for v in pois.values())}", file=OUT)
print("ids:", ",".join(c["id"] for c in cities), file=OUT)
missing = [c["id"] for c in cities if not pois.get(c["id"])]
print("缺景点数据的城市:", missing, file=OUT)

URLS = [
    ("datav_china_full", "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"),
    ("datav_china", "https://geo.datav.aliyun.com/areas_v3/bound/100000.json"),
    ("echarts_china", "https://cdn.jsdelivr.net/npm/echarts@4.9.0/map/json/china.json"),
]
with httpx.Client(timeout=25, follow_redirects=True) as c:
    for name, url in URLS:
        try:
            r = c.get(url, headers={"User-Agent": "wenlv/1.0"})
            info = f"{name:18} {r.status_code}  bytes={len(r.content)}"
            if r.status_code == 200:
                try:
                    j = r.json()
                    feats = j.get("features") or []
                    names = [f.get("properties", {}).get("name") for f in feats][:8]
                    info += f"  features={len(feats)}  sample={names}"
                except Exception as e:
                    info += f"  (json err {e})"
            print(info, file=OUT)
        except Exception as e:
            print(f"{name:18} FAIL {type(e).__name__}: {str(e)[:60]}", file=OUT)

OUT.close()
