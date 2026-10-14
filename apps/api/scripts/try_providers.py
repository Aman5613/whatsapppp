"""Try AI providers with real API keys (smoke test script).

Usage:
    python -m scripts.try_providers --provider openai --key sk-... --model gpt-4o-mini
    python -m scripts.try_providers --provider anthropic --key sk-ant-... --model claude-3-5-haiku-20241022
    python -m scripts.try_providers --provider gemini --key AIza... --model gemini-2.0-flash
"""

import argparse
import asyncio
import sys

from app.services.ai.registry import get_provider
from app.services.ai.types import Msg, ToolSpec


async def run_smoke_test(provider_name: str, api_key: str, model: str | None = None) -> None:
    """Run plain reply and tool calling smoke test against live provider."""
    print("\n=======================================================")
    print(f"Testing Provider: {provider_name.upper()} (Model: {model or 'default'})")
    print("=======================================================")

    provider = get_provider(provider_name, api_key=api_key, model=model)

    # 1. Plain Text Reply Test
    print("\n[1/2] Testing plain conversation response...")
    system_prompt = "You are a friendly customer support assistant for an Indian retail brand."
    messages = [
        Msg(role="user", content="Hello! Do you deliver to Bangalore? Answer in one sentence."),
    ]
    try:
        result = await provider.generate(system=system_prompt, messages=messages)
        print("  Status: SUCCESS")
        print(f"  Response: {result.text}")
        print(
            f"  Tokens:   {result.usage.input_tokens} input, {result.usage.output_tokens} output"
        )
        print(f"  Latency:  {result.latency_ms} ms")
    except Exception as exc:
        print(f"  Status: FAILED -> {exc}", file=sys.stderr)
        return

    # 2. Tool Calling Round Trip Test
    print("\n[2/2] Testing tool calling round trip...")
    tool = ToolSpec(
        name="search_products",
        description="Search for store products by query string and category",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term, e.g. shoes, shirt"},
                "max_price": {"type": "number", "description": "Maximum budget"},
            },
            "required": ["query"],
        },
    )
    tool_messages = [
        Msg(role="user", content="I want to buy running shoes under 2000 rupees. Can you check?"),
    ]
    try:
        tool_result = await provider.generate(
            system="Always use the search_products tool when a customer asks for item availability.",
            messages=tool_messages,
            tools=[tool],
        )
        print("  Status: SUCCESS")
        print(f"  Stop Reason: {tool_result.stop_reason.value}")
        print(f"  Tool Calls:  {len(tool_result.tool_calls)}")
        for tc in tool_result.tool_calls:
            print(f"    - Function:  {tc.name}")
            print(f"    - Arguments: {tc.arguments}")

        # If tool was called, return simulated tool output for final response
        if tool_result.tool_calls:
            first_call = tool_result.tool_calls[0]
            tool_messages.append(
                Msg(
                    role="assistant",
                    content=tool_result.text,
                    tool_calls=tool_result.tool_calls,
                )
            )
            tool_messages.append(
                Msg(
                    role="tool_result",
                    tool_call_id=first_call.id,
                    content='{"products": [{"name": "Puma Velocity Nitro", "price": 1899, "stock": 4}]}',
                )
            )
            print("  Sending tool result back to LLM...")
            final_res = await provider.generate(
                system="State the findings from the tool concisely.",
                messages=tool_messages,
                tools=[tool],
            )
            print(f"  Final Answer: {final_res.text}")
    except Exception as exc:
        print(f"  Status: FAILED -> {exc}", file=sys.stderr)
        return

    print("\n All checks passed for provider!")


def main():
    parser = argparse.ArgumentParser(description="Test AI Provider with real key")
    parser.add_argument("--provider", required=True, choices=["openai", "anthropic", "gemini"])
    parser.add_argument("--key", required=True, help="Live API Key")
    parser.add_argument("--model", default=None, help="Model name override")

    args = parser.parse_args()
    asyncio.run(run_smoke_test(args.provider, args.key, args.model))


if __name__ == "__main__":
    main()
