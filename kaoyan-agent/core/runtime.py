"""Request-local execution state and shared, bounded model attempt counters."""

from contextvars import ContextVar
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import date, datetime, timezone
from threading import Lock
from typing import Callable

from core.errors import ModelBudgetExceeded

stream_sink = ContextVar("stream_sink", default=None)
quota_exempt = ContextVar("quota_exempt", default=False)
request_model_calls = ContextVar("request_model_calls", default=None)
execution_budget = ContextVar("execution_budget", default=None)
phase_budget = ContextVar("phase_budget", default=None)
model_timeout = ContextVar("model_timeout", default=None)
step_model_allowed: ContextVar[bool] = ContextVar("step_model_allowed", default=True)
# Why an otherwise eligible step was denied the model: "BUDGET" or "TIME" (None when not denied).
step_rules_reason: ContextVar[str | None] = ContextVar("step_rules_reason", default=None)
retrieval_budget = ContextVar("retrieval_budget", default=None)
admission_budget: ContextVar["CallBudget | None"] = ContextVar("admission_budget", default=None)


@contextmanager
def withhold_model_deltas() -> Iterator[None]:
    """Keep cancellable provider streaming while withholding unvalidated prose."""
    sink = stream_sink.get()
    if sink is None:
        yield
        return

    async def forward_stage(event: dict) -> None:
        """Only trusted lifecycle events may precede domain validation."""
        if event.get("type") == "stage":
            await sink(event)

    token = stream_sink.set(forward_stage)
    try:
        yield
    finally:
        stream_sink.reset(token)


class CallBudget:
    """Share one counter across child tasks; never copy an integer per expert."""

    def __init__(self, limit: int, used: int = 0) -> None:
        """Set the maximum and attempts already spent before a checkpoint."""
        self.limit = limit
        self.used = used
        self.lock = Lock()

    def consume(self) -> None:
        """Reserve one attempt before opening the provider request."""
        with self.lock:
            if self.used >= self.limit:
                raise ModelBudgetExceeded("request_model_limit")
            self.used += 1

    @staticmethod
    def reserve(*budgets: "CallBudget | None", daily: "ModelBudget | None" = None,
                daily_limit: int = 100, exempt: bool = False, commit: bool = True) -> None:
        """Atomically reserve global and phase allowances for parallel experts."""
        if daily is not None:
            daily.reserve_call(daily_limit, exempt, *budgets, commit=commit)
            return
        ordered = sorted(
            {id(budget): budget for budget in budgets if budget is not None}.values(),
            key=lambda budget: id(budget.lock),
        )
        for budget in ordered:
            budget.lock.acquire()
        try:
            if any(budget.used >= budget.limit for budget in ordered):
                raise ModelBudgetExceeded("request_model_limit")
            if commit:
                for budget in ordered:
                    budget.used += 1
        finally:
            for budget in reversed(ordered):
                budget.lock.release()


class ModelBudget:
    """Thread-safe UTC daily attempt budget for one Python process."""

    def __init__(self, today: Callable[[], date] | None = None) -> None:
        """Use UTC day boundaries, with an injectable clock for checks."""
        self.today = today or (lambda: datetime.now(timezone.utc).date())
        self.day = None
        self.calls = 0
        self.lock = Lock()

    def consume(self, limit: int) -> None:
        """Count failed attempts too; process restart retains the old limitation."""
        with self.lock:
            day = self.today()
            if day != self.day:
                self.day, self.calls = day, 0
            if self.calls >= limit:
                raise ModelBudgetExceeded("model_limit: 模型每日尝试次数已达上限")
            self.calls += 1

    def reserve_call(self, limit: int, exempt: bool, *budgets: CallBudget | None, commit: bool = True) -> None:
        """Atomically check daily/request/phase allowances before an actual call."""
        active = sorted({id(budget): budget for budget in budgets if budget is not None}.values(), key=id)
        locks = sorted([self.lock, *(budget.lock for budget in active)], key=id)
        for lock in locks:
            lock.acquire()
        try:
            day = self.today()
            if day != self.day:
                self.day, self.calls = day, 0
            if not exempt and self.calls >= limit:
                raise ModelBudgetExceeded("model_limit: 模型每日尝试次数已达上限")
            if any(budget.used >= budget.limit for budget in active):
                raise ModelBudgetExceeded("request_model_limit")
            if commit:
                for budget in active:
                    budget.used += 1
                if not exempt:
                    self.calls += 1
        finally:
            for lock in reversed(locks):
                lock.release()
