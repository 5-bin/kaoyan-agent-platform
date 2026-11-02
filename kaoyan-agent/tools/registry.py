"""Typed tool adapters over the actual HelloAgents base and registry."""

import asyncio
import inspect
import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from core.framework import Tool, ToolParameter, ToolRegistry
from schemas import StrictModel


class EmptyParameters(StrictModel):
    """No client-controlled parameters are accepted."""


class InstructionParameters(StrictModel):
    """Instruction already validated by the conversation request."""

    instruction: str = Field(min_length=1, max_length=8000)


def encode(value: object) -> str:
    """Serialize typed results at the framework tool boundary."""
    return json.dumps(
        value,
        ensure_ascii=False,
        default=lambda item: item.model_dump()
        if isinstance(item, BaseModel)
        else str(item),
    )


class ValidatedTool(Tool):
    """A registered tool validates both before execution and after serialization."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: type[BaseModel],
        callback: Callable,
        decoder: Callable = lambda value: value,
    ) -> None:
        """Declare a native tool with typed inputs and an injected implementation."""
        super().__init__(name, description)
        self.parameters = parameters
        self.callback = callback
        self.decoder = decoder

    def get_parameters(self) -> list[ToolParameter]:
        """Expose the pinned framework's parameter descriptors."""
        properties = self.parameters.model_json_schema().get("properties", {})
        return [
            ToolParameter(
                name=name,
                type=properties[name].get("type", "object"),
                description=properties[name].get("description", name),
                required=field.is_required(),
            )
            for name, field in self.parameters.model_fields.items()
        ]

    def run(self, parameters: dict[str, Any]) -> str:
        """Execute a synchronous tool with validated keyword arguments."""
        args = self.parameters.model_validate(parameters)
        if inspect.iscoroutinefunction(self.callback):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(self.arun(parameters))
            raise RuntimeError("use_arun_for_async_tool")
        return encode(self.callback(**args.model_dump()))

    async def arun(self, parameters: dict[str, Any]) -> str:
        """Keep blocking retrieval work away from the event loop."""
        args = self.parameters.model_validate(parameters)
        if inspect.iscoroutinefunction(self.callback):
            return encode(await self.callback(**args.model_dump()))
        return await asyncio.to_thread(self.run, parameters)

    def invoke(self, parameters: dict[str, Any]) -> Any:
        """Compatibility decoding for existing fixed tool callers."""
        return self.decoder(json.loads(self.run(parameters)))

    async def ainvoke(self, parameters: dict[str, Any]) -> Any:
        """Decode the native string result back into a checked domain type."""
        return self.decoder(json.loads(await self.arun(parameters)))


class StrictToolRegistry(ToolRegistry):
    """Use framework registration/discovery without global mutable registries."""

    def register_tool(self, tool: Tool) -> None:
        """Reject duplicates rather than the tutorial's silent replacement."""
        if (
            self.get_tool(tool.name) is not None
            or self.get_function(tool.name) is not None
        ):
            raise ValueError("duplicate_tool")
        # The pinned 0.2.8 base prints on every registration; agents build
        # request-scoped registries, so store directly in its _tools mapping.
        self._tools[tool.name] = tool

    def add(self, tool: ValidatedTool) -> ValidatedTool:
        """Register and return the exact native tool instance."""
        self.register_tool(tool)
        return tool

    def execute_tool(self, name: str, input_text: str) -> str:
        """Preserve the framework signature, but reject unknown names/arguments."""
        tool = self.get_tool(name)
        if tool is None:
            raise ValueError("unknown_tool")
        return tool.run(json.loads(input_text))

    async def execute_async(self, name: str, parameters: dict) -> Any:
        """Dispatch only already-registered, validated tools."""
        tool = self.get_tool(name)
        if not isinstance(tool, ValidatedTool):
            raise ValueError("unknown_tool")
        return await tool.ainvoke(parameters)
