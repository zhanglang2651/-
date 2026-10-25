"""节气算法验证：对照权威二十四节气表。"""
from __future__ import annotations

import io
import sys

sys.path.insert(0, r"D:\文旅助手")
from app.services.seasonal import current_term, _terms_of_year  # noqa: E402

OUT = io.open(r"D:\shot_tmp\term_test.txt", "w", encoding="utf-8", buffering=1)

# 权威参考（北京时间，2026 年）
TRUTH_2026 = {
    "小寒": "2026-01-05", "大寒": "2026-01-20", "立春": "2026-02-04",
    "雨水": "2026-02-18", "惊蛰": "2026-03-05", "春分": "2026-03-20",
    "清明": "2026-04-05", "谷雨": "2026-04-20", "立夏": "2026-05-05",
    "小满": "2026-05-21", "芒种": "2026-06-05", "夏至": "2026-06-21",
    "小暑": "2026-07-07", "大暑": "2026-07-23", "立秋": "2026-08-07",
    "处暑": "2026-08-23", "白露": "2026-09-07", "秋分": "2026-09-23",
    "寒露": "2026-10-08", "霜降": "2026-10-23", "立冬": "2026-11-07",
    "小雪": "2026-11-22", "大雪": "2026-12-07", "冬至": "2026-12-22",
}

print("=== 2026 年节气计算 vs 权威表 ===", file=OUT)
calc = dict(_terms_of_year(2026))
ok = bad = 0
for name, truth in TRUTH_2026.items():
    got = calc.get(name, "MISSING")
    if got == truth:
        ok += 1
        flag = "OK"
    else:
        bad += 1
        flag = "DIFF"
    print(f"{flag:5s} {name}  算={got}  真={truth}", file=OUT)
print(f"\n一致 {ok} / 不一致 {bad}", file=OUT)

print("\n=== 当前节气（2026-10-25）===", file=OUT)
ct = current_term()
for k, v in ct.items():
    if k != "year_terms":
        print(f"  {k}: {v}", file=OUT)
print(f"  year_terms 共 {len(ct['year_terms'])} 条", file=OUT)
OUT.close()
