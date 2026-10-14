"""AI Provider custom exception hierarchy."""


class LLMError(Exception):
    """Base exception for all AI provider errors."""

    def __init__(self, message: str, provider: str = "", status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class AuthError(LLMError):
    """Raised when provider rejects API key (401 / 403)."""

    pass


class RateLimitError(LLMError):
    """Raised when provider rate limit is exceeded (429)."""

    pass


class ProviderUnavailableError(LLMError):
    """Raised on provider server error (500, 502, 503, 504) or connection timeout."""

    pass


class InvalidRequestError(LLMError):
    """Raised on invalid request schema or unsupported parameter (400)."""

    pass
