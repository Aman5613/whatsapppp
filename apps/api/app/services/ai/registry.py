"""AI provider factory and registry."""

from app.core.crypto import decrypt_value
from app.models.business import Business
from app.services.ai.adapters.anthropic import AnthropicAdapter
from app.services.ai.adapters.gemini import GeminiAdapter
from app.services.ai.adapters.openai import OpenAIAdapter
from app.services.ai.errors import InvalidRequestError
from app.services.ai.protocol import LLMProvider


def get_provider(
    provider_name: str,
    api_key: str,
    model: str | None = None,
    timeout: float = 30.0,
) -> LLMProvider:
    """Build and return an LLMProvider adapter instance."""
    normalized = provider_name.strip().lower()

    if normalized == "openai":
        return OpenAIAdapter(
            api_key=api_key,
            model=model or "gpt-4o-mini",
            timeout=timeout,
        )
    elif normalized == "anthropic":
        return AnthropicAdapter(
            api_key=api_key,
            model=model or "claude-3-5-haiku-20241022",
            timeout=timeout,
        )
    elif normalized == "gemini":
        return GeminiAdapter(
            api_key=api_key,
            model=model or "gemini-2.0-flash",
            timeout=timeout,
        )
    else:
        raise InvalidRequestError(
            f"Unsupported AI provider: '{provider_name}'. Supported: openai, anthropic, gemini"
        )


def get_providers_for_business(
    business: Business,
) -> tuple[LLMProvider | None, LLMProvider | None]:
    """Instantiate primary and optional fallback providers using business decrypted keys."""
    primary_key = decrypt_value(business.ai_api_key_enc)
    primary: LLMProvider | None = None
    if primary_key:
        primary = get_provider(
            provider_name=business.ai_provider,
            api_key=primary_key,
            model=business.ai_model,
        )

    fallback: LLMProvider | None = None
    if business.fallback_provider:
        fallback_key = decrypt_value(business.fallback_key_enc)
        if fallback_key:
            fallback = get_provider(
                provider_name=business.fallback_provider,
                api_key=fallback_key,
                model=business.fallback_model,
            )

    return primary, fallback
