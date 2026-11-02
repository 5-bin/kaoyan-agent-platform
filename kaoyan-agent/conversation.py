"""Compatibility facade for the request-scoped HelloAgents coordinator."""

from agents.coordinator import ConversationCoordinator
from schemas import ConversationRequest, ConversationResolution
from workflows import Workflows


class ConversationWorkflow:
    """Keep Java and legacy Python callers on the existing entrypoints."""

    def __init__(self, engine: Workflows) -> None:
        """Reuse application dependencies without retaining a coordinator history."""
        self.engine = engine

    async def run(self, req: ConversationRequest) -> dict:
        """Run one isolated coordinator, never share native conversation history."""
        return await ConversationCoordinator(self.engine).execute(req)

    async def plan(self, req: ConversationRequest) -> ConversationResolution:
        """Build a plan before Java reads authorized business snapshots."""
        return await ConversationCoordinator(self.engine).plan(req)

    async def resolve(
        self, req: ConversationRequest
    ) -> tuple[ConversationRequest, ConversationResolution]:
        """Compatibility inspection entrypoint."""
        return await ConversationCoordinator(self.engine).resolve(req)
