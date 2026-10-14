"""Normalized types for multi-provider AI layer."""

import enum
from dataclasses import dataclass, field
from typing import Any, Literal


class StopReason(enum.StrEnum):
    """Normalized stop reason for LLM generation."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    ERROR = "error"


@dataclass
class ToolCall:
    """Standardized tool call requested by LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of an executed tool call returned to LLM."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Msg:
    """Standardized conversation message for AI adapters."""

    role: Literal["user", "assistant", "tool_result"]
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # Populated when role == "tool_result"


@dataclass
class ToolSpec:
    """Standardized JSON Schema specification for tools."""

    name: str
    description: str
    parameters: dict[
        str, Any
    ]  # JSON Schema: {"type": "object", "properties": {...}, "required": [...]}


@dataclass
class Usage:
    """Token consumption accounting."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResult:
    """Standardized result returned by all AI provider adapters."""

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    provider: str = ""
    model: str = ""
    stop_reason: StopReason = StopReason.END_TURN
    latency_ms: int = 0
