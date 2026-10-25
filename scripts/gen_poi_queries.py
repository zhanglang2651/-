"""用轻量模型把中文景点名批量转成 Unsplash 可搜的英文检索词。

Unsplash 对中文查询几乎搜不到东西，必须用英文地标名。
输出 app/data/poi_queries.json: { city_id: { poi_name: ["query1", "query2"] } }
"""
from __future__ import annotations

import asyncio
import io
import json
import sys

sys.path.insert(0, r"D:\文旅助手")

from app.core.llm import get_fast_llm  # noqa: E402
from app.services import poi as poi_svc  # noqa: E402

OUT = io.open(r"D:\shot_tmp\poi_q_gen.txt", "w", encoding="utf-8", buffering=1)
TARGET = r"D:\文旅助手\app\data\poi_queries.json"

PROMPT = """你是图片检索词生成器。我给你一个中国景点，需要你给出 2 个英文检索词，用于在 Unsplash（欧美摄影社区）搜索该景点的实拍照片。

规则：
1. 用景点最广为人知的英文名，不要加城市名（除非景点本身以城市命名，如 "Terracotta Army"）
2. 如果是知名地标，直接用标准英文名：兵马俑→Terracotta Army，大熊猫基地→giant panda breeding base chengdu，漓江→Li River Guilin，黄果树瀑布→Huangguoshu Waterfall
3. 如果是小众景点，用它的类型+特征描述：苗寨→Miao ethnic village，溶洞→limestone cave，湿地公园→wetland park
4. 第一个词要精准（能搜到这个景点），第二个词是通用同类兜底（如 waterfall / temple / ancient town）
5. 全部小写，除了专有名词首字母

只输出 JSON 数组，格式：["query1","query2"]

景点：{name}
描述：{desc}"""


async def gen_for_city(city: dict) -> tuple[str, dict[str, list[str]]]:
    pois = poi_svc.get_pois(city["id"])
    llm = get_fast_llm(0.3)
    result: dict[str, list[str]] = {}
    for p in pois:
        try:
            msg = await llm.ainvoke(PROMPT.format(name=p["name"], desc=p.get("desc", "")))
            text = (msg.content or "").strip()
            import re
            m = re.search(r"\[.*\]", text, re.S)
            arr = json.loads(m.group(0)) if m else []
            arr = [str(x).strip() for x in arr if str(x).strip()][:2]
            if arr:
                result[p["name"]] = arr
        except Exception as e:  # noqa: BLE001
            print(f"  ! {city['name']}/{p['name']}: {str(e)[:70]}", file=OUT)
        await asyncio.sleep(0.05)
    return city["id"], result


async def main():
    cities = poi_svc.list_cities()
    print(f"共 {len(cities)} 城", file=OUT)
    data: dict[str, dict[str, list[str]]] = {}
    for i, c in enumerate(cities, 1):
        cid, res = await gen_for_city(c)
        data[cid] = res
        print(f"[{i}/{len(cities)}] {c['name']}: {len(res)}/{len(poi_svc.get_pois(cid))} 条", file=OUT)

    with io.open(TARGET, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))
    total = sum(len(v) for v in data.values())
    print(f"\n已写入 {TARGET}，共 {total} 条", file=OUT)


asyncio.run(main())
OUT.close()
