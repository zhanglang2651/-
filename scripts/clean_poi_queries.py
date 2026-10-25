"""清洗景点检索词：修掉中英混杂、拼写错误、过泛的兜底词。"""
from __future__ import annotations

import io
import json
import re

SRC = r"D:\文旅助手\app\data\poi_queries.json"
OUT = io.open(r"D:\shot_tmp\poi_q_clean.txt", "w", encoding="utf-8", buffering=1)

# 常见专名正确拼写（LLM 偶尔会音译错）
FIX = {
    "jiexiu tower": "jiaxiu pavilion guiyang",
    "jiaxiu tower": "jiaxiu pavilion guiyang",
    "guizhou province museum": "guizhou museum",
    "qingyan ancient town": "qingyan ancient town guizhou",
    "huangguoshu": "huangguoshu waterfall",
    "wuzhen": "wuzhen water town",
    "lijiang old town": "lijiang old town",
    "terracotta army": "terracotta army xian",
    "forbidden city": "forbidden city beijing",
    "tianhe潭": "tianhe tan waterfall",
    "tianhetan": "tianhe tan waterfall",
    "hemu long dun": "hailongtun fortress",
    "luzhangguan": "loushan pass",
    "guizhou museum": "guizhou provincial museum",
}

# 无效兜底词（太泛，搜出来全是无关图）
DROP_TAIL = {"park", "bridge", "garden", "museum", "meeting", "marketplace",
             "sunset", "waterfall", "ancient town", "night market", "temple",
             "old town", "lake", "mountain", "scenery", "lake", "food",
             "market", "street", "building", "view", "landscape"}

data = json.load(io.open(SRC, encoding="utf-8"))
fixed, dropped, cleaned = 0, 0, 0

for cid, pois in data.items():
    for name, queries in list(pois.items()):
        out = []
        for q in queries:
            q = q.strip().lower()
            if not q:
                continue
            # FIX 表修正（先查 FIX 再判中英混杂，避免顺序错乱）
            if q in FIX:
                q = FIX[q]
                fixed += 1
            # 中英混杂：还有中文字符
            elif re.search(r"[\u4e00-\u9fff]", q):
                # 尝试用 FIX 表替换；没有就跳过这个查询
                q2 = FIX.get(q)
                if q2:
                    q = q2
                    fixed += 1
                else:
                    dropped += 1
                    continue
            if q in DROP_TAIL:
                dropped += 1
                continue
            if q not in out:
                out.append(q)
        if out:
            pois[name] = out
            cleaned += 1
        else:
            del pois[name]
            dropped += 1

with io.open(SRC, "w", encoding="utf-8") as f:
    f.write(json.dumps(data, ensure_ascii=False, indent=2))

total = sum(len(v) for v in data.values())
poi_count = sum(len(v) for v in data.values())
print(f"清洗完成：{poi_count} 个景点，{total} 条查询", file=OUT)
print(f"修正拼写 {fixed} 条，丢弃无效 {dropped} 条", file=OUT)
print("\n抽样：", file=OUT)
for cid in list(data)[:2]:
    for n, q in list(data[cid].items())[:6]:
        print(f"  [{cid}] {n}: {q}", file=OUT)
OUT.close()
