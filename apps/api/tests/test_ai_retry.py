"""Tests for AI retry with backoff and fallback logic."""

import pytest

from app.services.ai.errors import (
    AuthError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.services.ai.retry import call_with_retry, generate_with_fallback
from app.services.ai.types import LLMResult, Msg


class MockProvider:
    """Mock provider with controllable failure behaviors."""

    def __init__(
        self,
        name: str,
        fail_count: int = 0,
        fail_exc: Exception | None = None,
        return_text: str = "ok",
    ):
        self.provider_name = name
        self.model = "mock-model"
        self.fail_count = fail_count
        self.fail_exc = fail_exc or ProviderUnavailableError("Simulated outage", provider=name)
        self.attempts = 0
        self.return_text = return_text

    async def generate(self, system: str, messages: list[Msg], tools=None) -> LLMResult:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise self.fail_exc
        return LLMResult(
            text=self.return_text,
            provider=self.provider_name,
            model=self.model,
        )


@pytest.mark.anyio
async def test_retry_succeeds_after_transient_failures():
    """Verify call_with_retry recovers after transient errors."""
    mock_p = MockProvider(
        "flaky_provider", fail_count=2, fail_exc=RateLimitError("429 Too Many Requests")
    )

    result = await call_with_retry(
        mock_p.generate,
        system="",
        messages=[Msg(role="user", content="Hi")],
        max_retries=3,
        initial_delay=0.01,  # fast delay for tests
    )

    assert result.text == "ok"
    assert mock_p.attempts == 3


@pytest.mark.anyio
async def test_retry_fails_immediately_on_auth_error():
    """Verify non-retryable AuthError fails on first attempt without sleeping."""
    mock_p = MockProvider("unauth_provider", fail_count=5, fail_exc=AuthError("401 Invalid Key"))

    with pytest.raises(AuthError):
        await call_with_retry(
            mock_p.generate,
            system="",
            messages=[],
            max_retries=3,
            initial_delay=0.01,
        )

    # Should only have made 1 attempt
    assert mock_p.attempts == 1


@pytest.mark.anyio
async def test_fallback_activates_when_primary_exhausts_retries():
    """Verify generate_with_fallback switches to fallback provider upon primary failure."""
    primary = MockProvider(
        "primary_provider", fail_count=5, fail_exc=ProviderUnavailableError("500 Crash")
    )
    fallback = MockProvider("fallback_provider", fail_count=0, return_text="Fallback answered")

    result = await generate_with_fallback(
        primary=primary,
        fallback=fallback,
        system="be brief",
        messages=[Msg(role="user", content="help")],
        max_retries=2,
    )

    assert result.text == "Fallback answered"
    assert result.provider == "fallback_provider"
    assert primary.attempts == 2
    assert fallback.attempts == 1
