"""Google Gemini REST API adapter."""

import logging
import time
import uuid
from typing import Any

import httpx

from app.services.ai.errors import (
    AuthError,
    InvalidRequestError,
    LLMError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.services.ai.types import LLMResult, Msg, StopReason, ToolCall, ToolSpec, Usage

logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAdapter:
    """Thin adapter for Google Gemini REST API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        base_url: str = _GEMINI_BASE_URL,
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.provider_name = "gemini"

    def _convert_messages(self, messages: list[Msg]) -> list[dict[str, Any]]:
        """Translate standardized Msg list to Gemini contents format."""
        gemini_contents: list[dict[str, Any]] = []

        for m in messages:
            if m.role == "user":
                gemini_contents.append({"role": "user", "parts": [{"text": m.content or ""}]})
            elif m.role == "assistant":
                parts: list[dict[str, Any]] = []
                if m.content:
                    parts.append({"text": m.content})
                for tc in m.tool_calls:
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc.name,
                                "args": tc.arguments,
                            }
                        }
                    )
                gemini_contents.append({"role": "model", "parts": parts or [{"text": ""}]})
            elif m.role == "tool_result":
                gemini_contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": m.tool_call_id or "tool_result",
                                    "response": {"output": m.content or ""},
                                }
                            }
                        ],
                    }
                )

        return gemini_contents

    def _convert_tools(self, tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
        """Translate ToolSpec list to Gemini functionDeclarations format."""
        if not tools:
            return None
        declarations = [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in tools
        ]
        return [{"function_declarations": declarations}]

    async def generate(
        self,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResult:
        """Call Gemini generateContent API and return normalized LLMResult."""
        url = f"{self.base_url}/{self.model}:generateContent"
        params = {"key": self.api_key}

        payload: dict[str, Any] = {
            "contents": self._convert_messages(messages),
        }
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}

        gemini_tools = self._convert_tools(tools)
        if gemini_tools:
            payload["tools"] = gemini_tools

        headers = {"Content-Type": "application/json"}

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, params=params, json=payload, headers=headers)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ProviderUnavailableError(
                f"Gemini connection error: {exc}", provider=self.provider_name
            ) from exc
        except Exception as exc:
            raise LLMError(f"Gemini request failed: {exc}", provider=self.provider_name) from exc

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Error status code mapping
        if response.status_code in (401, 403):
            raise AuthError(
                f"Gemini authentication failed: {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise RateLimitError(
                f"Gemini quota/rate limit exceeded: {response.text}",
                provider=self.provider_name,
                status_code=429,
            )
        if response.status_code == 400:
            error_text = response.text.lower()
            if "key" in error_text or "api_key" in error_text:
                raise AuthError(
                    f"Gemini API key error: {response.text}",
                    provider=self.provider_name,
                    status_code=400,
                )
            raise InvalidRequestError(
                f"Gemini invalid request: {response.text}",
                provider=self.provider_name,
                status_code=400,
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Gemini server error ({response.status_code}): {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )
        if not response.is_success:
            raise LLMError(
                f"Gemini error ({response.status_code}): {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )

        data = response.json()
        candidates = data.get("candidates", [])
        candidate = candidates[0] if candidates else {}
        parts = candidate.get("content", {}).get("parts", [])

        # Extract text and functionCalls
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for p in parts:
            if "text" in p:
                text_parts.append(p["text"])
            elif "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    )
                )

        full_text = "".join(text_parts).strip() if text_parts else None

        # Stop reason mapping
        finish_reason = candidate.get("finishReason", "STOP")
        if tool_calls:
            stop_reason = StopReason.TOOL_USE
        elif finish_reason == "MAX_TOKENS":
            stop_reason = StopReason.MAX_TOKENS
        else:
            stop_reason = StopReason.END_TURN

        # Token usage
        raw_usage = data.get("usageMetadata", {})
        usage = Usage(
            input_tokens=raw_usage.get("promptTokenCount", 0),
            output_tokens=raw_usage.get("candidatesTokenCount", 0),
        )

        return LLMResult(
            text=full_text,
            tool_calls=tool_calls,
            usage=usage,
            provider=self.provider_name,
            model=self.model,
            stop_reason=stop_reason,
            latency_ms=latency_ms,
        )
