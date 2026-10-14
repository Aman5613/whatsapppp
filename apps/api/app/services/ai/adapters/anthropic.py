"""Anthropic Messages API adapter."""

import logging
import time
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

_DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter:
    """Thin adapter for Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-haiku-20241022",
        base_url: str = _DEFAULT_ANTHROPIC_URL,
        timeout: float = 30.0,
        max_tokens: int = 1024,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.provider_name = "anthropic"

    def _convert_messages(self, messages: list[Msg]) -> list[dict[str, Any]]:
        """Translate standardized Msg list to Anthropic Messages format.

        Anthropic requires tool results to be enclosed in a 'user' message
        containing a content block of type 'tool_result'.
        """
        anthropic_msgs: list[dict[str, Any]] = []

        for m in messages:
            if m.role == "user":
                anthropic_msgs.append({"role": "user", "content": m.content or ""})
            elif m.role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                if m.content:
                    content_blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                anthropic_msgs.append(
                    {"role": "assistant", "content": content_blocks or (m.content or "")}
                )
            elif m.role == "tool_result":
                anthropic_msgs.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id or "",
                                "content": m.content or "",
                            }
                        ],
                    }
                )

        return anthropic_msgs

    def _convert_tools(self, tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
        """Translate ToolSpec list to Anthropic tool definitions (input_schema)."""
        if not tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    async def generate(
        self,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResult:
        """Call Anthropic Messages API and return normalized LLMResult."""
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": self._convert_messages(messages),
        }
        if system:
            payload["system"] = system

        tool_defs = self._convert_tools(tools)
        if tool_defs:
            payload["tools"] = tool_defs

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=payload, headers=headers)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ProviderUnavailableError(
                f"Anthropic connection error: {exc}", provider=self.provider_name
            ) from exc
        except Exception as exc:
            raise LLMError(
                f"Anthropic request failed: {exc}", provider=self.provider_name
            ) from exc

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Error status code mapping
        if response.status_code in (401, 403):
            raise AuthError(
                f"Anthropic auth failed: {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise RateLimitError(
                f"Anthropic rate limit exceeded: {response.text}",
                provider=self.provider_name,
                status_code=429,
            )
        if response.status_code == 400:
            raise InvalidRequestError(
                f"Anthropic invalid request: {response.text}",
                provider=self.provider_name,
                status_code=400,
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Anthropic server error ({response.status_code}): {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )
        if not response.is_success:
            raise LLMError(
                f"Anthropic error ({response.status_code}): {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )

        data = response.json()
        raw_content = data.get("content", [])

        # Extract text blocks and tool_use blocks
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in raw_content:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        full_text = "".join(text_parts).strip() if text_parts else None

        # Stop reason mapping
        anthropic_stop = data.get("stop_reason")
        if anthropic_stop == "tool_use" or tool_calls:
            stop_reason = StopReason.TOOL_USE
        elif anthropic_stop == "max_tokens":
            stop_reason = StopReason.MAX_TOKENS
        else:
            stop_reason = StopReason.END_TURN

        # Token usage
        raw_usage = data.get("usage", {})
        usage = Usage(
            input_tokens=raw_usage.get("input_tokens", 0),
            output_tokens=raw_usage.get("output_tokens", 0),
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
