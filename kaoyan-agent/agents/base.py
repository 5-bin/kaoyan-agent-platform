"""Native HelloAgents execution lifecycle for typed project domain handlers."""

import asyncio
import json
from typing import TYPE_CHECKING, Any

from config import Settings
from agents.results import finalize_result
from core.framework import Agent, Config, Message
from core.model import ModelClient
from retrieval import Corpus, Document
from schemas import ChatRequest, ConversationRequest, ConversationResolution
from tools.registry import ValidatedTool
from tools.schools import Admission

if TYPE_CHECKING:
    from workflows import Workflows

DomainContext = ChatRequest | tuple[ConversationRequest, ConversationResolution]


class StructuredAgent(Agent):
    """Keep native string execution while adapters expose existing dictionaries."""

    def __init__(
        self, owner: "Workflows | StructuredAgent", name: str | None = None
    ) -> None:
        """Bind shared read dependencies, with a fresh native message history."""
        self.owner = owner
        self.engine = getattr(owner, "engine", owner)
        super().__init__(
            name=name or type(self).__name__,
            llm=self.engine.model,
            config=Config(debug=False),
        )

    @property
    def settings(self) -> Settings:
        """Use the application's configuration, not tutorial environment defaults."""
        return self.engine.settings

    @property
    def model(self) -> ModelClient:
        """Preserve application/test dependency injection."""
        return self.engine.model

    @property
    def corpus(self) -> Corpus:
        """Use the active immutable corpus."""
        return self.engine.corpus

    @property
    def knowledge_search(self) -> ValidatedTool:
        """Use the registered application tool or its controlled test replacement."""
        return self.engine.knowledge_search

    @property
    def programs(self) -> list[tuple[Admission, Document]]:
        """Use the same validated admissions copy."""
        return self.engine.programs

    def base(
        self, request: ConversationRequest, resolution: ConversationResolution
    ) -> dict:
        """Apply conversation conditions using the coordinator's single rule."""
        return self.owner.base(request, resolution)

    def finish(
        self, result: dict, resolution: ConversationResolution | None = None
    ) -> dict:
        """Reuse conversation result validation/defaults."""
        return self.owner.finish(result, resolution)

    def run(self, input_text: str, **kwargs: Any) -> str:
        """Synchronous HelloAgents entry for callers outside an event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.arun(input_text, **kwargs))
        raise RuntimeError("use_arun_in_async_context")

    async def arun(self, input_text: str, **kwargs: Any) -> str:
        """Run one domain step; always clear request history, including cancellation."""
        self.add_message(Message(content=input_text, role="user"))
        try:
            context = kwargs.get("context")
            if not isinstance(context, (ChatRequest, tuple)):
                raise ValueError("agent_context_required")
            if isinstance(context, tuple) and (
                len(context) != 2
                or not isinstance(context[0], ConversationRequest)
                or not isinstance(context[1], ConversationResolution)
            ):
                raise ValueError("invalid_agent_context")
            value = await self.handle(context)
            request = context[0] if isinstance(context, tuple) else context
            if isinstance(context, tuple):
                value = self.finish(value, context[1])
            value = finalize_result(value, self.corpus.release_id, request.taskType)
            result = json.dumps(value, ensure_ascii=False)
            self.add_message(Message(content=result, role="assistant"))
            return result
        finally:
            self.clear_history()

    async def execute(self, context: DomainContext) -> dict:
        """Translate the native result to the existing service contract."""
        request = context[0] if isinstance(context, tuple) else context
        return json.loads(await self.arun(request.userInput or "", context=context))

    async def handle(self, context: DomainContext) -> dict:
        """Concrete experts implement a single bounded domain operation."""
        raise NotImplementedError
