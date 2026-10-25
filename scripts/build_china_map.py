"""生成中国省级地图的 SVG 路径数据。

数据源：阿里 DataV.GeoAtlas（国内可直连）
  https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json

处理：RDP 简化 → 经纬度线性映射 → SVG path，落盘到 web/assets/china-geo.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import httpx

SRC = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"
OUT = Path(r"D:\文旅助手\web\assets\china-geo.json")
CITIES = Path(r"D:\文旅助手\app\data\cities.json")

# 画布与经纬度范围（覆盖最西 73.5E、最北 53.6N、最南 18.2N）
W, H = 900, 520
LON0, LON1 = 73.0, 135.5
LAT0, LAT1 = 17.0, 54.5

# 省级后缀归一
SUFFIX = ("特别行政区", "维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "省", "市")


def norm(name: str) -> str:
    n = (name or "").strip()
    for s in SUFFIX:
        if n.endswith(s):
            return n[: -len(s)]
    return n


def px(lon: float) -> float:
    return (lon - LON0) / (LON1 - LON0) * W


def py(lat: float) -> float:
    return (LAT1 - lat) / (LAT1 - LAT0) * H


def perp_dist(p, a, b) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def rdp(points, eps):
    """Ramer–Douglas–Peucker 简化。"""
    if len(points) < 3:
        return points
    dmax, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        d = perp_dist(points[i], points[0], points[-1])
        if d > dmax:
            idx, dmax = i, d
    if dmax > eps:
        return rdp(points[: idx + 1], eps)[:-1] + rdp(points[idx:], eps)
    return [points[0], points[-1]]


def rings_of(geom: dict):
    t = geom.get("type")
    if t == "Polygon":
        return geom["coordinates"]
    if t == "MultiPolygon":
        return [r for poly in geom["coordinates"] for r in poly]
    return []


def main() -> None:
    with httpx.Client(timeout=40, follow_redirects=True) as c:
        r = c.get(SRC, headers={"User-Agent": "wenlv/1.0"})
        r.raise_for_status()
        geo = r.json()

    provinces: dict[str, str] = {}
    centers: dict[str, list[float]] = {}

    for feat in geo.get("features", []):
        props = feat.get("properties") or {}
        name = props.get("name") or ""
        if not name:
            continue
        paths = []
        for ring in rings_of(feat.get("geometry") or {}):
            pts = [(px(c[0]), py(c[1])) for c in ring if len(c) >= 2]
            if len(pts) < 3:
                continue
            simplified = rdp(pts, 0.9)  # 像素级容差
            d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in simplified) + "Z"
            paths.append(d)
        if paths:
            provinces[name] = "".join(paths)
        ctr = props.get("centroid") or props.get("center")
        if ctr and len(ctr) >= 2:
            centers[name] = [round(px(ctr[0]), 1), round(py(ctr[1]), 1)]

    # 城市所属省份 → 地图 key
    cities = json.loads(CITIES.read_text(encoding="utf-8"))
    key_by_norm = {norm(k): k for k in provinces}
    city_map = {}
    for c_ in cities:
        key = key_by_norm.get(norm(c_["province"]))
        if key:
            city_map[c_["id"]] = key

    payload = {
        "width": W, "height": H,
        "lon_range": [LON0, LON1], "lat_range": [LAT0, LAT1],
        "provinces": provinces,
        "centers": centers,
        "city_province": city_map,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"省份 {len(provinces)} 个，城市省份映射 {len(city_map)}/{len(cities)}，文件 {size_kb:.0f} KB")
    missing = [c_["name"] for c_ in cities if c_["id"] not in city_map]
    if missing:
        print("未匹配到省份:", missing)


if __name__ == "__main__":
    main()
