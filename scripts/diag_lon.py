"""诊断：视黄经公式在冬至附近的实际取值。"""
from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r"D:\文旅助手")
from app.services.seasonal import _apparent_lon, _jd_from_date  # noqa: E402

OUT = io.open(r"D:\shot_tmp\lon_diag.txt", "w", encoding="utf-8", buffering=1)

# 2026 年 12 月逐时打印视黄经（UTC）
for d in (20, 21, 22, 23):
    jd0 = _jd_from_date(2026, 12, d)
    for h in (0, 6, 12, 18):
        jd = jd0 + h / 24.0
        lon = _apparent_lon(jd)
        bj = datetime(2026, 12, d, h, 0, tzinfo=timezone.utc) + timedelta(hours=8)
        print(f"BJ {bj:%Y-%m-%d %H:%M}  lon={lon:.5f}  (target 270)", file=OUT)

# 找 270 上穿零的精确时刻
target = 270.0
lo = _jd_from_date(2026, 12, 15)
hi = _jd_from_date(2026, 12, 28)
prev_jd, prev_d = lo, ((_apparent_lon(lo) - target + 180) % 360) - 180
cur = lo
while cur <= hi:
    d = ((_apparent_lon(cur) - target + 180) % 360) - 180
    if prev_d < 0 <= d:
        a, b = prev_jd, cur
        for _ in range(50):
            mid = (a + b) / 2
            dd = ((_apparent_lon(mid) - target + 180) % 360) - 180
            if dd < 0:
                a = mid
            else:
                b = mid
        jd = (a + b) / 2
        bj = datetime(2026, 12, 15, tzinfo=timezone.utc) + timedelta(days=jd - lo)
        bj += timedelta(hours=8)
        print(f"\n黄经=270 时刻 (UT) = {bj - timedelta(hours=8):%Y-%m-%d %H:%M}", file=OUT)
        print(f"北京时间 = {bj:%Y-%m-%d %H:%M}", file=OUT)
        break
    prev_jd, prev_d = cur, d
    cur += 0.25
OUT.close()
