"""AI Provider abstraction layer."""

from app.services.ai.errors import (
    AuthError,
    InvalidRequestError,
    LLMError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.services.ai.protocol import LLMProvider
from app.services.ai.registry import get_provider, get_providers_for_business
from app.services.ai.retry import call_with_retry, generate_with_fallback
from app.services.ai.types import (
    LLMResult,
    Msg,
    StopReason,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)

__all__ = [
    "AuthError",
    "InvalidRequestError",
    "LLMError",
    "LLMProvider",
    "LLMResult",
    "Msg",
    "ProviderUnavailableError",
    "RateLimitError",
    "StopReason",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "Usage",
    "call_with_retry",
    "generate_with_fallback",
    "get_provider",
    "get_providers_for_business",
]
