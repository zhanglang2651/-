"""Agent 状态定义。"""
from __future__ import annotations

from typing import Any, TypedDict


class PlanState(TypedDict, total=False):
    # 输入
    query: str
    origin_hint: str
    # intake 产出
    brief: dict[str, Any]
    # context 产出
    city: dict[str, Any]
    weather: dict[str, Any]
    candidates: list[dict[str, Any]]
    # compose 产出
    plan: dict[str, Any]
    raw: str
    # review 产出
    errors: list[str]
    warnings: list[str]
    retries: int
    ok: bool
    # 运行时注入（事件回调，仅进程内使用）
    emit: Any
