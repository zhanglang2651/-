"""轻量滑动窗口限流。

单机内存实现：按 key（用户/IP/接口）统计窗口内的调用次数。
自建项目够用；多副本部署时换成 Redis 的 ZSET 即可。
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._last_gc = time.time()

    def allow(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """返回 (是否放行, 建议等待秒数)。"""
        now = time.time()
        self._gc(now)
        dq = self._hits[key]
        while dq and now - dq[0] > window:
            dq.popleft()
        if len(dq) >= limit:
            wait = int(dq[0] + window - now) + 1
            return False, max(wait, 1)
        dq.append(now)
        return True, 0

    def remaining(self, key: str, limit: int, window: int) -> int:
        now = time.time()
        dq = self._hits.get(key)
        if not dq:
            return limit
        while dq and now - dq[0] > window:
            dq.popleft()
        return max(0, limit - len(dq))

    def _gc(self, now: float) -> None:
        """每 10 分钟清一次空桶，避免长跑内存涨。"""
        if now - self._last_gc < 600:
            return
        self._last_gc = now
        for k in [k for k, dq in self._hits.items() if not dq]:
            self._hits.pop(k, None)


limiter = SlidingWindow()

# 配额策略
PLAN_PER_USER = 8       # 每用户每小时可生成行程次数
PLAN_WINDOW = 3600
LLM_PER_IP = 40         # 每 IP 每小时可调用 AI 接口总次数
REVISE_PER_USER = 30    # 单日修改额度（每小时）
