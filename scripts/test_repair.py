"""规则修补层单元测试：构造带硬伤的行程，验证能否就地修好。"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.graph import _rule_repair, validate  # noqa: E402
from app.services import poi as poi_svc  # noqa: E402

OUT = io.open(r"D:\文旅助手\_repair_test.txt", "w", encoding="utf-8", buffering=1)
city = poi_svc.get_city("guiyang")
cands = poi_svc.get_pois("guiyang")
brief = {"days": 2, "people": 2, "budget_level": "中等"}

bad_plan = {
    "city": "贵阳",
    "days": 2,
    "summary": "测试行程",
    "budget": {"total": 999, "breakdown": {"住宿": 380, "餐饮": 300}},
    "itinerary": [
        {
            "day": 1, "date": "2026-10-26", "title": "测试第一天",
            "items": [
                {"time": "09:00", "name": "贵阳市规划馆", "type": "人文", "hours": 2, "cost": 0},  # 幻觉
                {"time": "14:00", "name": "黔灵山公园", "type": "自然", "hours": 3, "cost": 5},
                {"time": "17:00", "name": "黔灵山公园", "type": "自然", "hours": 3, "cost": 5},  # 重复
            ],
            "meals": [{"time": "12:00", "name": "肠旺面", "place": "市区", "cost": 30}],
        },
        {
            "day": 2, "date": "2026-10-27", "title": "测试第二天",
            "items": [],  # 空
            "meals": [],   # 缺餐
        },
    ],
}

print("候选池:", [c["name"] for c in cands], file=OUT)
e0, w0 = validate(bad_plan, brief["days"], cands)
print("\n修补前 errors:", e0, file=OUT)
print("修补前 warnings:", w0, file=OUT)

fixed = _rule_repair(json.loads(json.dumps(bad_plan)), cands, city, brief["days"])
e1, w1 = validate(fixed, brief["days"], cands)
print("\n修补后 errors:", e1, file=OUT)
print("修补后 warnings:", w1, file=OUT)

for d in fixed["itinerary"]:
    print(f'\nDay {d["day"]}: {[i["name"] for i in d["items"]]}', file=OUT)
    print(f'  餐: {[m["name"] for m in d["meals"]]}', file=OUT)
print("\n预算:", json.dumps(fixed["budget"], ensure_ascii=False), file=OUT)
print("\n结论:", "PASS" if not e1 else "FAIL", file=OUT)
OUT.close()
