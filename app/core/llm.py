"""LLM 工厂：统一走硅基流动 OpenAI 兼容网关。"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import settings


def _build(model: str, temperature: float, streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=settings.api_key,          # type: ignore[arg-type]
        base_url=settings.base_url,
        temperature=temperature,
        streaming=streaming,
        timeout=120,
        max_retries=2,
    )


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.65) -> ChatOpenAI:
    """主力模型：行程规划、复杂推理。"""
    return _build(settings.model, temperature)


@lru_cache(maxsize=4)
def get_fast_llm(temperature: float = 0.8) -> ChatOpenAI:
    """轻量模型：热点播报、短文案。"""
    return _build(settings.model_fast, temperature)


@lru_cache(maxsize=2)
def get_streaming_llm(temperature: float = 0.6) -> ChatOpenAI:
    """开启原生流式的模型，供 SSE 逐 token 输出与 ReAct Agent 使用。"""
    return _build(settings.model, temperature, streaming=True)
