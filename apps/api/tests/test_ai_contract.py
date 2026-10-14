"""Shared contract test suite for OpenAI, Anthropic, and Gemini adapters."""

import httpx
import pytest

from app.services.ai.adapters import AnthropicAdapter, GeminiAdapter, OpenAIAdapter
from app.services.ai.errors import (
    AuthError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.services.ai.types import Msg, StopReason, ToolSpec

# Sample tool specification used in contract tests
SAMPLE_TOOL = ToolSpec(
    name="get_order_status",
    description="Look up status of customer order",
    parameters={
        "type": "object",
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"],
    },
)


@pytest.mark.anyio
async def test_openai_adapter_plain_reply(monkeypatch):
    """Test OpenAIAdapter plain response with usage extraction."""

    async def mock_post(self, url, json=None, headers=None, params=None):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Sure, we deliver to Mumbai!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 25, "completion_tokens": 12},
            },
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o-mini")
    res = await adapter.generate(
        system="You are helpful.",
        messages=[Msg(role="user", content="Deliver to Mumbai?")],
    )

    assert res.text == "Sure, we deliver to Mumbai!"
    assert res.stop_reason == StopReason.END_TURN
    assert len(res.tool_calls) == 0
    assert res.usage.input_tokens == 25
    assert res.usage.output_tokens == 12
    assert res.provider == "openai"


@pytest.mark.anyio
async def test_openai_adapter_tool_call_round_trip(monkeypatch):
    """Test OpenAIAdapter tool call generation and subsequent tool result handling."""
    call_count = 0

    async def mock_post(self, url, json=None, headers=None, params=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First response: LLM triggers tool call
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "call_ord_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_order_status",
                                            "arguments": '{"order_id": "ORD-999"}',
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 15},
                },
                request=httpx.Request("POST", str(url)),
            )
        else:
            # Second response: LLM receives tool result and produces final answer
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Your order ORD-999 has been shipped!",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 10},
                },
                request=httpx.Request("POST", str(url)),
            )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    adapter = OpenAIAdapter(api_key="sk-test")
    messages = [Msg(role="user", content="Where is my order ORD-999?")]

    # 1. First invocation triggers tool
    first_res = await adapter.generate(system="", messages=messages, tools=[SAMPLE_TOOL])
    assert first_res.stop_reason == StopReason.TOOL_USE
    assert len(first_res.tool_calls) == 1
    assert first_res.tool_calls[0].name == "get_order_status"
    assert first_res.tool_calls[0].arguments == {"order_id": "ORD-999"}

    # 2. Append tool result and request final answer
    messages.append(Msg(role="assistant", tool_calls=first_res.tool_calls))
    messages.append(
        Msg(role="tool_result", tool_call_id="call_ord_1", content='{"status": "shipped"}')
    )

    final_res = await adapter.generate(system="", messages=messages, tools=[SAMPLE_TOOL])
    assert final_res.text == "Your order ORD-999 has been shipped!"
    assert final_res.stop_reason == StopReason.END_TURN


@pytest.mark.anyio
async def test_anthropic_adapter_plain_and_tool_call(monkeypatch):
    """Test AnthropicAdapter plain response and tool calling."""

    async def mock_post(self, url, json=None, headers=None, params=None):
        if json and json.get("tools"):
            # Return tool use block
            return httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_abc",
                            "name": "get_order_status",
                            "input": {"order_id": "ORD-123"},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 40, "output_tokens": 20},
                },
                request=httpx.Request("POST", str(url)),
            )
        else:
            # Plain text response
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "Hello from Claude!"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 8},
                },
                request=httpx.Request("POST", str(url)),
            )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    adapter = AnthropicAdapter(api_key="sk-ant-test", model="claude-3-5-haiku-20241022")

    # Plain text
    plain_res = await adapter.generate(system="Be nice", messages=[Msg(role="user", content="Hi")])
    assert plain_res.text == "Hello from Claude!"
    assert plain_res.stop_reason == StopReason.END_TURN
    assert plain_res.usage.input_tokens == 10

    # Tool call
    tool_res = await adapter.generate(
        system="",
        messages=[Msg(role="user", content="Check ORD-123")],
        tools=[SAMPLE_TOOL],
    )
    assert tool_res.stop_reason == StopReason.TOOL_USE
    assert len(tool_res.tool_calls) == 1
    assert tool_res.tool_calls[0].name == "get_order_status"
    assert tool_res.tool_calls[0].arguments == {"order_id": "ORD-123"}


@pytest.mark.anyio
async def test_gemini_adapter_plain_and_tool_call(monkeypatch):
    """Test GeminiAdapter plain response and functionCall response."""

    async def mock_post(self, url, json=None, headers=None, params=None):
        if json and json.get("tools"):
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "get_order_status",
                                            "args": {"order_id": "ORD-GEMINI"},
                                        }
                                    }
                                ]
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 35, "candidatesTokenCount": 18},
                },
                request=httpx.Request("POST", str(url)),
            )
        else:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "Namaste! Welcome to our store."}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 15, "candidatesTokenCount": 9},
                },
                request=httpx.Request("POST", str(url)),
            )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    adapter = GeminiAdapter(api_key="AIzaSyTestKey", model="gemini-2.0-flash")

    # Plain
    res = await adapter.generate(system="Be cordial", messages=[Msg(role="user", content="Hello")])
    assert res.text == "Namaste! Welcome to our store."
    assert res.stop_reason == StopReason.END_TURN
    assert res.usage.input_tokens == 15

    # Tool
    tool_res = await adapter.generate(
        system="",
        messages=[Msg(role="user", content="Check order")],
        tools=[SAMPLE_TOOL],
    )
    assert tool_res.stop_reason == StopReason.TOOL_USE
    assert len(tool_res.tool_calls) == 1
    assert tool_res.tool_calls[0].name == "get_order_status"
    assert tool_res.tool_calls[0].arguments == {"order_id": "ORD-GEMINI"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "adapter_cls,kwargs,status_code,expected_error",
    [
        (OpenAIAdapter, {"api_key": "k"}, 401, AuthError),
        (OpenAIAdapter, {"api_key": "k"}, 429, RateLimitError),
        (OpenAIAdapter, {"api_key": "k"}, 500, ProviderUnavailableError),
        (AnthropicAdapter, {"api_key": "k"}, 403, AuthError),
        (AnthropicAdapter, {"api_key": "k"}, 429, RateLimitError),
        (AnthropicAdapter, {"api_key": "k"}, 503, ProviderUnavailableError),
        (GeminiAdapter, {"api_key": "k"}, 400, AuthError),  # 400 key error
        (GeminiAdapter, {"api_key": "k"}, 429, RateLimitError),
        (GeminiAdapter, {"api_key": "k"}, 502, ProviderUnavailableError),
    ],
)
async def test_adapter_error_mappings(
    adapter_cls, kwargs, status_code, expected_error, monkeypatch
):
    """Verify all adapters translate vendor HTTP status codes to standardized error types."""

    async def mock_post(self, url, json=None, headers=None, params=None):
        error_body = "API key not valid" if status_code == 400 else "Service error"
        return httpx.Response(
            status_code,
            text=error_body,
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    adapter = adapter_cls(**kwargs)
    with pytest.raises(expected_error):
        await adapter.generate(system="", messages=[Msg(role="user", content="Hi")])
