"""
Modular tool registry for the voice agent pipeline.

To add a new tool:
  1. Define an async handler function: async def my_tool(arg1: str) -> str
  2. Call registry.register(...) with the OpenAI-compatible schema and handler

The registry is consumed by LLMAdapter, which passes schemas to the LLM and
dispatches tool calls back through the registry automatically.
"""

from __future__ import annotations

import random
from typing import Awaitable, Callable


class ToolRegistry:
    """Dynamic registry mapping tool names → schemas + async handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, _ToolEntry] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Awaitable[str]],
    ) -> None:
        """Register a tool with its OpenAI-compatible function schema and handler."""
        self._tools[name] = _ToolEntry(
            schema={
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            handler=handler,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_schemas(self) -> list[dict]:
        """Return the list of OpenAI-format tool schemas for all registered tools."""
        return [entry.schema for entry in self._tools.values()]

    def has_tools(self) -> bool:
        return bool(self._tools)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, name: str, arguments: dict) -> str:
        """Execute a registered tool by name.  Returns the result string."""
        if name not in self._tools:
            return f"Error: unknown tool '{name}'"
        try:
            return await self._tools[name].handler(**arguments)
        except Exception as exc:  # noqa: BLE001
            return f"Error executing tool '{name}': {exc}"


class _ToolEntry:
    __slots__ = ("schema", "handler")

    def __init__(self, schema: dict, handler: Callable[..., Awaitable[str]]) -> None:
        self.schema = schema
        self.handler = handler


# ---------------------------------------------------------------------------
# Default tool implementations  (swap these for real APIs in production)
# ---------------------------------------------------------------------------

async def get_current_weather(location: str, unit: str = "fahrenheit") -> str:
    """Simulated weather lookup — replace with a real API in production."""
    temp = random.randint(60, 85) if unit == "fahrenheit" else random.randint(15, 30)
    symbol = "°F" if unit == "fahrenheit" else "°C"
    condition = random.choice(["sunny", "cloudy", "partly cloudy", "rainy", "windy"])
    import json
    return json.dumps({
        "location": location,
        "temperature": temp,
        "unit": symbol,
        "condition": condition
    })


async def set_reminder(task: str, time: str) -> str:
    """Simulated reminder — replace with real persistence in production."""
    return f"Reminder set: '{task}' at {time}."


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_default_registry() -> ToolRegistry:
    """Build a registry pre-loaded with the default demo tools."""
    registry = ToolRegistry()

    registry.register(
        name="get_current_weather",
        description="Get the current weather in a given location",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                },
            },
            "required": ["location"],
        },
        handler=get_current_weather,
    )

    registry.register(
        name="set_reminder",
        description="Set a reminder for a specific time",
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task to be reminded about",
                },
                "time": {
                    "type": "string",
                    "description": "The time for the reminder in HH:MM format",
                },
            },
            "required": ["task", "time"],
        },
        handler=set_reminder,
    )

    return registry
