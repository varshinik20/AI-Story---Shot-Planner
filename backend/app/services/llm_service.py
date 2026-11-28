"""Centralized LLM provider adapter, retry/timeout wrapper, and DB usage logger."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, BadRequestError, RateLimitError
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.exceptions import LLMUnavailableError, LLMUpstreamError
from app.db.models.domain import ModelUsageLog
from app.services.openai_client import get_openai_client, is_reasoning_model

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Published per-1M-token USD pricing for known OpenAI models.
# Unknown models return estimated_cost_usd = None instead of inventing numbers.
OPENAI_MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-2024-11-20": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
}


def estimate_cost_usd(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Compute exact estimated USD cost when token counts and known pricing exist."""
    if input_tokens is None or output_tokens is None:
        return None
    pricing = OPENAI_MODEL_PRICING_PER_1M.get(model)
    if pricing is None:
        # Prefix match for dated snapshots of base models
        for prefix, rates in OPENAI_MODEL_PRICING_PER_1M.items():
            if model.startswith(prefix):
                pricing = rates
                break
    if pricing is None:
        return None
    in_rate, out_rate = pricing
    return round((input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate, 6)


@dataclass(slots=True)
class LLMCallResult:
    """Normalized response returned by a provider adapter."""

    content: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    execution_time_ms: int
    estimated_cost_usd: float | None
    request_id: str


class LLMProviderAdapter(Protocol):
    """Provider abstraction so OpenAI or alternative LLM backends are swappable."""

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
        json_mode: bool,
    ) -> LLMCallResult: ...


_MODELS_WITHOUT_TEMPERATURE: set[str] = set()


class OpenAIProviderAdapter:
    """OpenAI Chat Completions adapter using AsyncOpenAI."""

    def __init__(
        self,
        api_key: str,
        client: AsyncOpenAI | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._client = client
        self._settings = settings

    def _get_client(self, timeout_seconds: float) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise LLMUnavailableError(
                "OPENAI_API_KEY is not configured. Add it to backend/.env to enable AI generation.",
                code="LLM_API_KEY_MISSING",
            )
        if self._settings is not None:
            # Process-wide pooled client: reuses keep-alive connections across requests.
            return get_openai_client(self._settings)
        return AsyncOpenAI(api_key=self._api_key, timeout=timeout_seconds, max_retries=0)

    def _is_reasoning(self, model: str) -> bool:
        if model in _MODELS_WITHOUT_TEMPERATURE:
            return True
        return self._settings is not None and is_reasoning_model(self._settings, model)

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
        json_mode: bool,
    ) -> LLMCallResult:
        client = self._get_client(timeout_seconds)
        request_id = str(uuid.uuid4())
        started = time.perf_counter()

        reasoning = self._is_reasoning(model)
        # Reasoning tokens count toward the completion budget, so keep a safe floor.
        effective_max = max(max_tokens, 6000) if reasoning else max_tokens
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": effective_max,
            "timeout": timeout_seconds,
        }
        if reasoning:
            kwargs["reasoning_effort"] = (
                self._settings.OPENAI_REASONING_EFFORT if self._settings is not None else "low"
            )
        else:
            kwargs["temperature"] = temperature
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            msg = str(exc).lower()
            retry_kwargs = dict(kwargs)
            changed = False
            if "temperature" in msg:
                logger.warning(
                    "Model '%s' rejected temperature; set OPENAI_MODEL_IS_REASONING=true to avoid this extra round trip.",
                    model,
                )
                _MODELS_WITHOUT_TEMPERATURE.add(model)
                retry_kwargs.pop("temperature", None)
                retry_kwargs["reasoning_effort"] = (
                    self._settings.OPENAI_REASONING_EFFORT if self._settings is not None else "low"
                )
                retry_kwargs["max_completion_tokens"] = max(max_tokens, 6000)
                changed = True
            if "reasoning_effort" in msg:
                retry_kwargs.pop("reasoning_effort", None)
                changed = True
            if "max_completion_tokens" in msg and "unsupported" in msg:
                retry_kwargs.pop("max_completion_tokens", None)
                retry_kwargs["max_tokens"] = max_tokens
                changed = True
            if not changed:
                raise
            response = await client.chat.completions.create(**retry_kwargs)

        content = response.choices[0].message.content if response.choices else None
        if (not content or not content.strip()) and response.choices and getattr(response.choices[0], "finish_reason", None) == "length":
            retry_kwargs = dict(kwargs)
            retry_kwargs["max_completion_tokens"] = max(effective_max * 2, 12000)
            response = await client.chat.completions.create(**retry_kwargs)
            content = response.choices[0].message.content if response.choices else None

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if not content or not content.strip():
            raise LLMUpstreamError("OpenAI returned an empty completion payload.")

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        output_tokens = getattr(usage, "completion_tokens", None) if usage else None
        actual_model = getattr(response, "model", None) or model

        return LLMCallResult(
            content=content,
            model=actual_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            execution_time_ms=elapsed_ms,
            estimated_cost_usd=estimate_cost_usd(actual_model, input_tokens, output_tokens),
            request_id=request_id,
        )


def _strip_json_fences(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


class LLMService:
    """Central service executing LLM calls with retries, schema validation, and DB logging."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        adapter: LLMProviderAdapter | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.adapter: LLMProviderAdapter = adapter or OpenAIProviderAdapter(
            api_key=settings.OPENAI_API_KEY,
            settings=settings,
        )

    async def _record_usage(
        self,
        *,
        request_id: str,
        project_id: uuid.UUID | None,
        engine: str,
        operation: str,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
        estimated_cost_usd: float | None,
        execution_time_ms: int,
        scene_id: str | None = None,
        shot_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        log = ModelUsageLog(
            request_id=request_id,
            project_id=project_id,
            engine=engine,
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            execution_time_ms=execution_time_ms,
            scene_id=scene_id,
            shot_id=shot_id,
            success=success,
            error_message=error_message,
        )
        if not success and self.session.bind is not None:
            factory = async_sessionmaker(bind=self.session.bind, class_=AsyncSession, expire_on_commit=False)
            async with factory() as err_session:
                try:
                    err_session.add(log)
                    await err_session.commit()
                except IntegrityError:
                    await err_session.rollback()
                    fallback_log = ModelUsageLog(
                        request_id=request_id,
                        project_id=None,
                        engine=engine,
                        operation=operation,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_usd=estimated_cost_usd,
                        execution_time_ms=execution_time_ms,
                        scene_id=scene_id,
                        shot_id=shot_id,
                        success=success,
                        error_message=error_message,
                    )
                    err_session.add(fallback_log)
                    await err_session.commit()
            return
        self.session.add(log)
        await self.session.flush()

    async def _call_with_retry(
        self,
        *,
        messages: list[dict[str, str]],
        engine: str,
        operation: str,
        project_id: uuid.UUID | None = None,
        scene_id: str | None = None,
        shot_id: str | None = None,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMCallResult:
        target_model = model or self.settings.OPENAI_MODEL
        target_tokens = max_tokens or self.settings.LLM_MAX_TOKENS
        attempts = max(1, self.settings.LLM_MAX_RETRIES + 1)
        last_exc: Exception | None = None

        for attempt in range(attempts):
            started = time.perf_counter()
            req_id = str(uuid.uuid4())
            try:
                result = await self.adapter.complete(
                    messages=messages,
                    model=target_model,
                    temperature=temperature,
                    max_tokens=target_tokens,
                    timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
                    json_mode=json_mode,
                )
                await self._record_usage(
                    request_id=result.request_id,
                    project_id=project_id,
                    engine=engine,
                    operation=operation,
                    model=result.model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    estimated_cost_usd=result.estimated_cost_usd,
                    execution_time_ms=result.execution_time_ms,
                    scene_id=scene_id,
                    shot_id=shot_id,
                    success=True,
                )
                return result
            except LLMUnavailableError as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                await self._record_usage(
                    request_id=req_id,
                    project_id=project_id,
                    engine=engine,
                    operation=operation,
                    model=target_model,
                    input_tokens=None,
                    output_tokens=None,
                    estimated_cost_usd=None,
                    execution_time_ms=elapsed_ms,
                    scene_id=scene_id,
                    shot_id=shot_id,
                    success=False,
                    error_message=exc.message,
                )
                raise
            except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
                last_exc = exc
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "Transient LLM failure on %s/%s (attempt %d/%d): %s",
                    engine,
                    operation,
                    attempt + 1,
                    attempts,
                    exc,
                )
                await self._record_usage(
                    request_id=req_id,
                    project_id=project_id,
                    engine=engine,
                    operation=operation,
                    model=target_model,
                    input_tokens=None,
                    output_tokens=None,
                    estimated_cost_usd=None,
                    execution_time_ms=elapsed_ms,
                    scene_id=scene_id,
                    shot_id=shot_id,
                    success=False,
                    error_message=str(exc),
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(min(2**attempt, 4) * 0.5)
                    continue
                raise LLMUnavailableError(
                    f"AI provider is temporarily unavailable: {exc}",
                    code="LLM_CONNECTION_ERROR",
                ) from exc
            except APIError as exc:
                last_exc = exc
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                await self._record_usage(
                    request_id=req_id,
                    project_id=project_id,
                    engine=engine,
                    operation=operation,
                    model=target_model,
                    input_tokens=None,
                    output_tokens=None,
                    estimated_cost_usd=None,
                    execution_time_ms=elapsed_ms,
                    scene_id=scene_id,
                    shot_id=shot_id,
                    success=False,
                    error_message=str(exc),
                )
                status_code = getattr(exc, "status_code", None)
                if status_code in (401, 403, 429):
                    raise LLMUnavailableError(
                        f"AI provider authentication or quota error: {exc}",
                        code="LLM_PROVIDER_AUTH_OR_QUOTA",
                    ) from exc
                raise LLMUpstreamError(f"AI provider error: {exc}") from exc
            except Exception as exc:
                last_exc = exc
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                await self._record_usage(
                    request_id=req_id,
                    project_id=project_id,
                    engine=engine,
                    operation=operation,
                    model=target_model,
                    input_tokens=None,
                    output_tokens=None,
                    estimated_cost_usd=None,
                    execution_time_ms=elapsed_ms,
                    scene_id=scene_id,
                    shot_id=shot_id,
                    success=False,
                    error_message=str(exc),
                )
                raise LLMUpstreamError(f"Unexpected AI failure: {exc}") from exc

        raise LLMUpstreamError(f"AI call failed: {last_exc}")

    async def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema_model: type[T],
        engine: str,
        operation: str,
        project_id: uuid.UUID | None = None,
        scene_id: str | None = None,
        shot_id: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> tuple[T, LLMCallResult]:
        """Execute an LLM call enforcing JSON output validated against a Pydantic model."""
        current_messages = list(messages)
        schema_json = json.dumps(schema_model.model_json_schema())
        if current_messages and current_messages[0].get("role") == "system":
            current_messages[0] = {
                "role": "system",
                "content": (
                    f"{current_messages[0]['content']}\n\n"
                    f"REQUIRED JSON SCHEMA (must match exact top-level keys & types):\n{schema_json}"
                ),
            }
        for parse_attempt in range(2):
            result = await self._call_with_retry(
                messages=current_messages,
                engine=engine,
                operation=operation,
                project_id=project_id,
                scene_id=scene_id,
                shot_id=shot_id,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
            cleaned = _strip_json_fences(result.content)
            try:
                payload = json.loads(cleaned)
                validated = schema_model.model_validate(payload)
                return validated, result
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "LLM JSON validation error on %s/%s (parse_attempt=%d): %s",
                    engine,
                    operation,
                    parse_attempt + 1,
                    exc,
                )
                if parse_attempt == 0:
                    current_messages = [
                        *current_messages,
                        {"role": "assistant", "content": result.content},
                        {
                            "role": "user",
                            "content": (
                                "Your previous JSON response did not match the required schema "
                                f"({exc}). Return ONLY valid JSON strictly matching the schema."
                            ),
                        },
                    ]
                    continue
                raise LLMUpstreamError(
                    f"AI response failed schema validation for {schema_model.__name__}: {exc}",
                    code="LLM_SCHEMA_VALIDATION_FAILED",
                ) from exc
        raise LLMUpstreamError("Failed to parse LLM JSON output.")

    async def generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        engine: str,
        operation: str,
        project_id: uuid.UUID | None = None,
        scene_id: str | None = None,
        shot_id: str | None = None,
        model: str | None = None,
        temperature: float = 0.6,
        max_tokens: int | None = None,
    ) -> LLMCallResult:
        """Execute a natural-language text LLM call with usage logging."""
        return await self._call_with_retry(
            messages=messages,
            engine=engine,
            operation=operation,
            project_id=project_id,
            scene_id=scene_id,
            shot_id=shot_id,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )
