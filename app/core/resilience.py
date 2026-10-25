"""LLM 调用的可靠性包装：失败重试 + token 计量。

计量口径：优先读 OpenAI 兼容返回里的 token_usage；
部分网关不返回 usage 时退回按字符数估算（中文约 1.6 字/token）。
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)


class UsageStats:
    def __init__(self) -> None:
        self.day = date.today().isoformat()
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.failures = 0
        self._lock = asyncio.Lock()

    def _roll(self) -> None:
        today = date.today().isoformat()
        if today != self.day:
            self.day = today
            self.calls = self.prompt_tokens = self.completion_tokens = self.failures = 0

    def record(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self._roll()
        self.calls += 1
        self.prompt_tokens += max(0, prompt_tokens)
        self.completion_tokens += max(0, completion_tokens)

    def record_failure(self) -> None:
        self._roll()
        self.failures += 1

    def snapshot(self) -> dict[str, Any]:
        self._roll()
        return {
            "day": self.day,
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "failures": self.failures,
        }


stats = UsageStats()


def estimate_tokens(text: str) -> int:
    """粗估：中文 1 字≈0.6 token，英文 4 字符≈1 token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk * 0.65 + other / 3.5) + 1


class TransientError(Exception):
    """上游临时故障，可重试。"""


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=1, max=8),
       retry=retry_if_exception_type((TransientError, TimeoutError, ConnectionError)),
       reraise=True)
async def ainvoke(llm, prompt, **kwargs):
    """带重试的 ainvoke；顺带记账。"""
    try:
        msg = await asyncio.wait_for(llm.ainvoke(prompt, **kwargs), timeout=120)
    except asyncio.TimeoutError as exc:
        stats.record_failure()
        raise TransientError("模型响应超时") from exc
    except (TimeoutError, ConnectionError) as exc:
        stats.record_failure()
        raise TransientError(str(exc)) from exc

    usage = {}
    meta = getattr(msg, "response_metadata", None) or {}
    usage = meta.get("token_usage") or meta.get("usage") or {}
    if not usage:
        # 回退估算
        prompt_text = prompt if isinstance(prompt, str) else str(prompt)
        stats.record(estimate_tokens(prompt_text), estimate_tokens(str(msg.content or "")))
    else:
        stats.record(int(usage.get("prompt_tokens") or 0),
                     int(usage.get("completion_tokens") or 0))
    return msg
