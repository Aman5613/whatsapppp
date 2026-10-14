"""OpenAI Chat Completions API adapter."""

import json
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

_DEFAULT_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIAdapter:
    """Thin adapter for OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = _DEFAULT_OPENAI_URL,
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.provider_name = "openai"

    def _convert_messages(self, system: str, messages: list[Msg]) -> list[dict[str, Any]]:
        """Translate standardized Msg list to OpenAI messages format."""
        openai_msgs: list[dict[str, Any]] = []

        if system:
            openai_msgs.append({"role": "system", "content": system})

        for m in messages:
            if m.role == "user":
                openai_msgs.append({"role": "user", "content": m.content or ""})
            elif m.role == "assistant":
                item: dict[str, Any] = {"role": "assistant"}
                if m.content:
                    item["content"] = m.content
                if m.tool_calls:
                    item["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments)
                                if isinstance(tc.arguments, dict)
                                else str(tc.arguments),
                            },
                        }
                        for tc in m.tool_calls
                    ]
                openai_msgs.append(item)
            elif m.role == "tool_result":
                openai_msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id or "",
                        "content": m.content or "",
                    }
                )

        return openai_msgs

    def _convert_tools(self, tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
        """Translate ToolSpec list to OpenAI function calling format."""
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    async def generate(
        self,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResult:
        """Call OpenAI Chat Completions API and return normalized LLMResult."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages(system, messages),
        }
        tool_defs = self._convert_tools(tools)
        if tool_defs:
            payload["tools"] = tool_defs

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=payload, headers=headers)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ProviderUnavailableError(
                f"OpenAI connection error: {exc}", provider=self.provider_name
            ) from exc
        except Exception as exc:
            raise LLMError(f"OpenAI request failed: {exc}", provider=self.provider_name) from exc

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Error status code mapping
        if response.status_code in (401, 403):
            raise AuthError(
                f"OpenAI authentication failed: {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise RateLimitError(
                f"OpenAI rate limit exceeded: {response.text}",
                provider=self.provider_name,
                status_code=429,
            )
        if response.status_code == 400:
            raise InvalidRequestError(
                f"OpenAI invalid request: {response.text}",
                provider=self.provider_name,
                status_code=400,
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"OpenAI server error ({response.status_code}): {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )
        if not response.is_success:
            raise LLMError(
                f"OpenAI error ({response.status_code}): {response.text}",
                provider=self.provider_name,
                status_code=response.status_code,
            )

        data = response.json()
        choice = data.get("choices", [{}])[0]
        msg_obj = choice.get("message", {})

        # Extract tool calls
        tool_calls: list[ToolCall] = []
        raw_tool_calls = msg_obj.get("tool_calls", [])
        for rtc in raw_tool_calls:
            fn = rtc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {"raw": fn.get("arguments", "")}
            tool_calls.append(
                ToolCall(
                    id=rtc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=args,
                )
            )

        # Stop reason mapping
        finish_reason = choice.get("finish_reason")
        if finish_reason == "tool_calls" or tool_calls:
            stop_reason = StopReason.TOOL_USE
        elif finish_reason == "length":
            stop_reason = StopReason.MAX_TOKENS
        else:
            stop_reason = StopReason.END_TURN

        # Token usage
        raw_usage = data.get("usage", {})
        usage = Usage(
            input_tokens=raw_usage.get("prompt_tokens", 0),
            output_tokens=raw_usage.get("completion_tokens", 0),
        )

        return LLMResult(
            text=msg_obj.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            provider=self.provider_name,
            model=self.model,
            stop_reason=stop_reason,
            latency_ms=latency_ms,
        )
