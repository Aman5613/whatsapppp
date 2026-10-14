"""Tests for AI provider registry and factory."""

import pytest

from app.core.crypto import encrypt_value
from app.models.business import Business
from app.services.ai.adapters import AnthropicAdapter, GeminiAdapter, OpenAIAdapter
from app.services.ai.errors import InvalidRequestError
from app.services.ai.registry import get_provider, get_providers_for_business


def test_get_provider_valid():
    """Verify get_provider instantiates appropriate adapter."""
    openai_p = get_provider("openai", api_key="sk-test", model="gpt-4o")
    assert isinstance(openai_p, OpenAIAdapter)
    assert openai_p.model == "gpt-4o"

    anthropic_p = get_provider("anthropic", api_key="sk-ant", model="claude-3-5-sonnet")
    assert isinstance(anthropic_p, AnthropicAdapter)
    assert anthropic_p.model == "claude-3-5-sonnet"

    gemini_p = get_provider("gemini", api_key="AIza", model="gemini-2.0-flash")
    assert isinstance(gemini_p, GeminiAdapter)
    assert gemini_p.model == "gemini-2.0-flash"


def test_get_provider_unsupported_raises():
    """Unsupported provider raises InvalidRequestError."""
    with pytest.raises(InvalidRequestError):
        get_provider("mistral", api_key="key")


def test_get_providers_for_business():
    """Verify registry decrypts keys and builds primary and fallback providers."""
    biz = Business(
        name="Multi AI Biz",
        ai_provider="openai",
        ai_model="gpt-4o-mini",
        ai_api_key_enc=encrypt_value("sk-primary-key"),
        fallback_provider="gemini",
        fallback_model="gemini-2.0-flash",
        fallback_key_enc=encrypt_value("AIza-fallback-key"),
    )

    primary, fallback = get_providers_for_business(biz)

    assert primary is not None
    assert isinstance(primary, OpenAIAdapter)
    assert primary.api_key == "sk-primary-key"

    assert fallback is not None
    assert isinstance(fallback, GeminiAdapter)
    assert fallback.api_key == "AIza-fallback-key"


def test_get_providers_for_business_no_keys():
    """Returns None when keys are not configured."""
    biz = Business(name="No Key Biz")
    primary, fallback = get_providers_for_business(biz)
    assert primary is None
    assert fallback is None
