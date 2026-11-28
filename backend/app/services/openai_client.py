"""Shared OpenAI client and model-capability helpers.

A single pooled ``AsyncOpenAI`` client is reused per process so every request reuses warm
HTTP/2 keep-alive connections instead of paying a fresh TCP + TLS handshake per LLM call.
Model capabilities (reasoning vs. sampling models) are resolved up front from configuration,
so requests are correct on the first attempt instead of discovering them via 400 responses.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.config import Settings

logger = logging.getLogger(__name__)

# Model families that reject `temperature` and accept `reasoning_effort` instead.
_REASONING_MODEL_PREFIXES: tuple[str, ...] = ("o1", "o3", "o4", "gpt-5", "gpt-6")

_client: AsyncOpenAI | None = None
_client_key: tuple[str, float, int] | None = None


def is_reasoning_model(settings: Settings, model: str) -> bool:
    """Explicit OPENAI_MODEL_IS_REASONING wins; otherwise detect by model family prefix."""
    if settings.OPENAI_MODEL_IS_REASONING is not None:
        return settings.OPENAI_MODEL_IS_REASONING
    return model.strip().lower().startswith(_REASONING_MODEL_PREFIXES)


def sampling_params(settings: Settings, model: str, temperature: float) -> dict[str, Any]:
    """Return the correct sampling / reasoning kwargs for the target model."""
    if is_reasoning_model(settings, model):
        return {"reasoning_effort": settings.OPENAI_REASONING_EFFORT}
    return {"temperature": temperature}


def get_openai_client(settings: Settings) -> AsyncOpenAI:
    """Return the process-wide pooled AsyncOpenAI client (rebuilt only if credentials change)."""
    global _client, _client_key
    key = (settings.OPENAI_API_KEY.strip(), float(settings.LLM_TIMEOUT_SECONDS), settings.OPENAI_MAX_CONNECTIONS)
    if _client is None or _client_key != key:
        _client = AsyncOpenAI(
            api_key=key[0],
            timeout=key[1],
            # Retries are owned by LLMService so they are logged and bounded in one place.
            max_retries=0,
            http_client=httpx.AsyncClient(
                timeout=key[1],
                limits=httpx.Limits(
                    max_connections=settings.OPENAI_MAX_CONNECTIONS,
                    max_keepalive_connections=settings.OPENAI_MAX_CONNECTIONS,
                    keepalive_expiry=60.0,
                ),
            ),
        )
        _client_key = key
    return _client


async def close_openai_client() -> None:
    """Close pooled connections on application shutdown."""
    global _client, _client_key
    if _client is not None:
        try:
            await _client.close()
        finally:
            _client = None
            _client_key = None
            logger.info("OpenAI client connection pool closed.")
