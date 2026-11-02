"""Practice specialist proposes reviewed candidates; Java executes confirmed actions."""

from agents.base import StructuredAgent
from agents.learning_result import local_learning_result
from schemas import ConversationRequest, ConversationResolution


class PracticeAgent(StructuredAgent):
    """Propose operations over Java-authorized candidates without calling a model."""

    async def handle(
        self, state: tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Keep candidate/count validation in the plan and authoritative Java layer."""
        request, plan = state
        _, result, _ = local_learning_result(request, plan, self.base(request, plan))
        result.update(
            operation=plan.operation,
            questionRefs=list(plan.questionRefs),
            count=plan.count,
            target=plan.target,
        )
        return result
