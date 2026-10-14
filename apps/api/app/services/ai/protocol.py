"""LLMProvider Protocol definition."""

from typing import Protocol, runtime_checkable

from app.services.ai.types import LLMResult, Msg, ToolSpec


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all provider adapters must implement."""

    provider_name: str
    model: str

    async def generate(
        self,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResult:
        """Generate response from the LLM given conversation messages and optional tools."""
        ...
