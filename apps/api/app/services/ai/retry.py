"""Retry with exponential backoff and fallback provider execution."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.services.ai.errors import (
    AuthError,
    InvalidRequestError,
    LLMError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.services.ai.protocol import LLMProvider
from app.services.ai.types import LLMResult, Msg, ToolSpec

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3
_INITIAL_DELAY = 1.0  # seconds
_BACKOFF_FACTOR = 2.0


async def call_with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    initial_delay: float = _INITIAL_DELAY,
    **kwargs: Any,
) -> LLMResult:
    """Execute provider call with exponential backoff for transient errors."""
    delay = initial_delay
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (RateLimitError, ProviderUnavailableError) as exc:
            last_error = exc
            if attempt == max_retries:
                logger.error(
                    "Exhausted %d retries for provider %s: %s",
                    max_retries,
                    getattr(exc, "provider", "unknown"),
                    exc,
                )
                raise
            logger.warning(
                "Transient error on attempt %d/%d (%s). Retrying in %.2fs...",
                attempt,
                max_retries,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= _BACKOFF_FACTOR
        except (AuthError, InvalidRequestError):
            # Non-retryable errors
            raise
        except LLMError as exc:
            last_error = exc
            logger.error("Non-transient LLM error: %s", exc)
            raise

    if last_error:
        raise last_error
    raise LLMError("Unknown error occurred during provider execution")


async def generate_with_fallback(
    primary: LLMProvider,
    fallback: LLMProvider | None,
    system: str,
    messages: list[Msg],
    tools: list[ToolSpec] | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> LLMResult:
    """Attempt primary provider with retries; switch to fallback provider if primary fails."""
    try:
        return await call_with_retry(
            primary.generate,
            system=system,
            messages=messages,
            tools=tools,
            max_retries=max_retries,
        )
    except Exception as primary_exc:
        if not fallback:
            raise primary_exc

        logger.warning(
            "Primary provider %s failed (%s). Attempting fallback provider: %s...",
            primary.provider_name,
            primary_exc,
            fallback.provider_name,
        )
        try:
            return await call_with_retry(
                fallback.generate,
                system=system,
                messages=messages,
                tools=tools,
                max_retries=2,  # Fewer retries on fallback
            )
        except Exception as fallback_exc:
            logger.error(
                "Both primary (%s) and fallback (%s) providers failed.",
                primary.provider_name,
                fallback.provider_name,
            )
            raise primary_exc from fallback_exc
