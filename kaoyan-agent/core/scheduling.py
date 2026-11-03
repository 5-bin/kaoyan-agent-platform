"""Bounded dependency scheduling with serial provider work and pure-rule batches."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import monotonic

from core.errors import MODEL_FAILURES, ToolUnavailable
from core.mcp_runtime import McpCallError
from core.runtime import CallBudget, execution_budget, model_timeout, step_model_allowed, step_rules_reason
from schemas import ExpertStep

log = logging.getLogger(__name__)
# A model request is not started when less stage time remains (measured steps up to 8.5 s).
MIN_MODEL_SECONDS = 8.0
MODEL_PRIORITY = {name: index for index, name in enumerate(("LEARNING", "SCHOOL", "KNOWLEDGE", "STUDY_PLAN", "NOTE", "PRACTICE"))}


def unavailable(notice: str) -> dict:
    """Represent an uncompleted item without introducing a new public outcome."""
    return {"outcome": "UNSUPPORTED", "answer": notice, "notice": notice,
            "explanationMode": "rules", "references": []}


async def schedule_steps(
    steps: list[ExpertStep], execute: Callable[[ExpertStep, dict[str, dict]], Awaitable[dict]],
    model_eligible: Callable[[ExpertStep], bool], pure_rule: Callable[[ExpertStep], bool],
    phase_allowance: CallBudget, stage_seconds: float, step_seconds: float,
    min_model_seconds: float = 0.0, reasons: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Execute every explicit item; isolate timeouts and propagate cancellation/bugs.

    An eligible step denied the model records "BUDGET" or "TIME" in ``reasons`` and
    in ``step_rules_reason`` so the expert can state why it used rules.
    """
    completed: dict[str, dict] = {}
    pending = list(steps)
    deadline = monotonic() + stage_seconds

    def permission(step: ExpertStep) -> tuple[bool, str | None]:
        """Decide model use for one step and the reason when an eligible step is denied."""
        if not model_eligible(step) or step.agent == "PRACTICE":
            return False, None
        if pure_rule(step) or phase_allowance.used >= phase_allowance.limit:
            return False, "BUDGET"
        if deadline - monotonic() < min_model_seconds:
            return False, "TIME"
        return True, None

    async def run(step: ExpertStep, allow_model: bool, reason: str | None) -> None:
        started = monotonic()
        budget = execution_budget.get()
        used = budget.used if budget else 0
        failure = ""
        remaining = min(step_seconds, deadline - monotonic())
        if remaining <= 0:
            completed[step.agent] = unavailable("专家阶段超时，本项未完成。")
            return
        if any(completed[name]["outcome"] != "COMPLETED" for name in step.dependsOn):
            completed[step.agent] = unavailable("依赖尚未完成，本项未执行。")
            return
        if reason and reasons is not None:
            reasons[step.agent] = reason
        gate = step_model_allowed.set(allow_model)
        why = step_rules_reason.set(reason)
        timeout = model_timeout.set(remaining)
        try:
            completed[step.agent] = await asyncio.wait_for(execute(step, completed), remaining)
        except asyncio.CancelledError:
            failure = "CancelledError"
            raise
        except TimeoutError:
            failure = "TimeoutError"
            completed[step.agent] = unavailable("专家单步超时，本项未完成。")
        except MODEL_FAILURES + (McpCallError, ToolUnavailable) as error:
            failure = type(error).__name__
            completed[step.agent] = unavailable(step.agent + "：暂时不可用")
        except Exception as error:
            failure = type(error).__name__
            raise
        finally:
            model_timeout.reset(timeout)
            step_rules_reason.reset(why)
            step_model_allowed.reset(gate)
            value = completed.get(step.agent, {})
            log.info("expert=%s outcome=%s mode=%s elapsed_ms=%d attempts=%d failure=%s",
                     step.agent, value.get("outcome", "FAILED"), value.get("explanationMode", "rules"),
                     int((monotonic() - started) * 1000), (budget.used if budget else 0) - used, failure)

    while pending:
        if monotonic() >= deadline:
            for step in pending:
                completed[step.agent] = unavailable("专家阶段超时，本项未完成。")
            break
        ready = [step for step in pending if set(step.dependsOn) <= completed.keys()]
        if not ready:
            raise ValueError("invalid_expert_dependencies")
        # Finish the highest-priority model candidate (or its prerequisites)
        # before offering unused allowance to lower-priority candidates.
        candidates = [step for step in pending if model_eligible(step)]
        preferred = min(candidates, key=lambda step: MODEL_PRIORITY[step.agent]) if candidates else ready[0]
        by_name = {step.agent: step for step in pending}
        while preferred not in ready:
            preferred = by_name[next(name for name in preferred.dependsOn if name not in completed)]
        batch = [step for step in ready if pure_rule(step)]
        if preferred not in batch:
            batch.append(preferred)
        tasks = [asyncio.create_task(run(step, *permission(step))) for step in batch]
        try:
            await asyncio.gather(*tasks)
        finally:
            # gather does not cancel siblings when one raises. Never leak a
            # private input/history or a late provider result past this request.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        pending = [step for step in pending if step.agent not in completed]
    return completed
