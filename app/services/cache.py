"""进程内 TTL 缓存 + 单飞（single-flight），避免热点接口被并发打爆上游。"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Tuple


class TTLCache:
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expire_at, value = item
        if time.time() > expire_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (time.time() + ttl, value)

    def age(self, key: str) -> float | None:
        item = self._store.get(key)
        if not item:
            return None
        return round(time.time() - (item[0] - 0), 1)

    async def get_or_set(self, key: str, ttl: int, factory: Callable[[], Awaitable[Any]]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            value = await factory()
            self.set(key, value, ttl)
            return value

    def clear(self) -> None:
        self._store.clear()


cache = TTLCache()
