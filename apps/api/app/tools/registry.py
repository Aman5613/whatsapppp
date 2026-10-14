"""Central LLM Tool Registry and execution dispatcher."""

import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.tool_call import ToolCall
from app.services.ai.types import ToolSpec
from app.tools.get_order_status import SPEC as ORDER_SPEC
from app.tools.get_order_status import execute as execute_order
from app.tools.handoff_to_human import SPEC as HANDOFF_SPEC
from app.tools.handoff_to_human import execute as execute_handoff
from app.tools.search_products import SPEC as PRODUCT_SPEC
from app.tools.search_products import execute as execute_product

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry maintaining tool schemas and executing tool calls with audit logging."""

    def __init__(self):
        self._specs: dict[str, ToolSpec] = {}
        self._executors: dict[str, Callable] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the core business data and handoff tools."""
        self.register(PRODUCT_SPEC, execute_product)
        self.register(ORDER_SPEC, execute_order)
        self.register(HANDOFF_SPEC, execute_handoff)

    def register(self, spec: ToolSpec, executor: Callable) -> None:
        """Register a tool specification and its execution function."""
        self._specs[spec.name] = spec
        self._executors[spec.name] = executor

    def get_specs(self) -> list[ToolSpec]:
        """Return list of JSON Schema tool specs for the LLM."""
        return list(self._specs.values())

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        session: AsyncSession,
        business_id: uuid.UUID,
        customer_phone: str,
        conversation: Conversation,
    ) -> tuple[dict[str, Any], bool]:
        """Execute a tool call, persist to tool_calls table, and return (result_dict, is_ok)."""
        executor = self._executors.get(name)
        if not executor:
            err_result = {"error": f"Tool '{name}' is not recognized."}
            return err_result, False

        ok = True
        try:
            if name == "handoff_to_human":
                result = await executor(
                    session=session,
                    conversation=conversation,
                    args=args,
                )
            elif name == "search_products" or name == "get_order_status":
                result = await executor(
                    session=session,
                    business_id=business_id,
                    customer_phone=customer_phone,
                    args=args,
                )
            else:
                result = await executor(
                    session=session,
                    business_id=business_id,
                    customer_phone=customer_phone,
                    args=args,
                )
        except Exception as exc:
            logger.error("Error executing tool %s: %s", name, exc, exc_info=True)
            result = {"error": f"Tool execution failed: {str(exc)}"}
            ok = False

        # Persist audit record in tool_calls table
        try:
            log_record = ToolCall(
                conversation_id=conversation.id,
                tool=name,
                args=args,
                result=result,
                ok=ok,
            )
            session.add(log_record)
            await session.flush()
        except Exception as log_exc:
            logger.warning("Failed to record tool_call audit log: %s", log_exc)

        return result, ok


# Global singleton tool registry
tool_registry = ToolRegistry()
