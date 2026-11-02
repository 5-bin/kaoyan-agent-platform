"""Compatibility exports; implementation lives in the HelloAgents core adapter."""

from openai import AsyncOpenAI

from config import Settings
from core.model import ModelClient as CoreModelClient
from core.model import T
from core.runtime import ModelBudget, quota_exempt, request_model_calls, stream_sink
from core.streaming import parse_result as _parse
from core.streaming import project

__all__ = [
    "ModelClient",
    "ModelBudget",
    "stream_sink",
    "quota_exempt",
    "request_model_calls",
    "_parse",
    "project",
]


class ModelClient(CoreModelClient):
    """Keep the existing injection point for controlled SDK transports."""

    def __init__(self, settings: Settings) -> None:
        """Keep the legacy transport injection seam on the new application client."""
        super().__init__(
            settings, client_factory=lambda **kwargs: AsyncOpenAI(**kwargs)
        )

    async def _generate(
        self, instruction: str, payload: dict, schema: type[T], router: bool = False
    ) -> T:
        """Keep the historical private test seam on the same bounded implementation."""
        return await self.generate(instruction, payload, schema, router)
