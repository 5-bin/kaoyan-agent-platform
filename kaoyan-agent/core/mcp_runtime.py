"""Bounded MCP calls and independently owned, non-reconnecting stdio sessions."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from time import monotonic
from typing import TypeVar
from uuid import uuid4

import anyio
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp.shared.message import MessageMetadata
from mcp.shared.session import CONNECTION_CLOSED, ProgressFnT
from pydantic import BaseModel

from core.runtime import CallBudget

log = logging.getLogger(__name__)
ResponseT = TypeVar("ResponseT", bound=BaseModel)
DecodedT = TypeVar("DecodedT")


class McpState(StrEnum):
    """Connection availability, independent of the last tool's business result."""

    DISABLED = "DISABLED"
    STARTING = "STARTING"
    READY = "READY"
    UNAVAILABLE = "UNAVAILABLE"
    CLOSED = "CLOSED"


class McpErrorCode(StrEnum):
    """Safe diagnostic categories; external messages never become error codes."""

    START_FAILED = "START_FAILED"
    CATALOG_CHANGED = "CATALOG_CHANGED"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    CONNECTION_CLOSED = "CONNECTION_CLOSED"
    TIMEOUT = "TIMEOUT"
    CALL_LIMIT = "CALL_LIMIT"
    TOOL_FAILED = "TOOL_FAILED"
    RESULT_INVALID = "RESULT_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class McpCallError(RuntimeError):
    """A fixed failure category usable by workflows without exposing SDK data."""

    def __init__(self, code: McpErrorCode) -> None:
        """Retain only a trusted category and no underlying exception content."""
        self.code = code
        super().__init__(code.value)


@dataclass
class McpStatus:
    """Small in-memory health snapshot, with no queries, paths or credentials."""

    enabled: bool
    state: McpState
    error_code: McpErrorCode | None = None

    def snapshot(self) -> dict[str, bool | str | None]:
        """Serialize additive health fields without making a protocol request."""
        return {
            "enabled": self.enabled,
            "state": self.state.value,
            "errorCode": self.error_code.value if self.error_code else None,
        }


class SafeSdkDiagnostics(logging.Filter):
    """Sanitize the pinned SDK's root-logger protocol validation messages only."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Remove peer payloads and exception chains before handlers receive them."""
        if record.pathname.replace("\\", "/").endswith("/mcp/shared/session.py"):
            record.msg = "mcpProtocolDiagnostic=REJECTED"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


class CancellingClientSession(ClientSession):
    """Extend pinned MCP 1.12.4 cancellation and receive-loop completion hooks."""

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        """Install an owner callback before entering the SDK context."""
        self._disconnect_callback = callback

    async def _receive_loop(self) -> None:
        """Keep the pinned private signature; notify even on idle EOF or cancel."""
        try:
            await super()._receive_loop()
        finally:
            self._disconnect_callback()

    async def _validate_tool_result(self, name: str, result: types.CallToolResult) -> None:
        """Keep 1.12.4's hook signature and hide raw schema-validation details."""
        try:
            await super()._validate_tool_result(name, result)
        except RuntimeError:
            raise McpCallError(McpErrorCode.RESULT_INVALID) from None

    async def send_request(
        self,
        request: types.ClientRequest,
        result_type: type[ResponseT],
        request_read_timeout_seconds: timedelta | None = None,
        metadata: MessageMetadata | None = None,
        progress_callback: ProgressFnT | None = None,
    ) -> ResponseT:
        """Preserve the SDK signature and cancel only the matching tool request."""
        # 1.12.4 reserves this counter before the first await in send_request.
        request_id = self._request_id
        try:
            return await super().send_request(
                request, result_type,
                request_read_timeout_seconds=request_read_timeout_seconds,
                metadata=metadata, progress_callback=progress_callback,
            )
        except (asyncio.CancelledError, McpError) as error:
            timed_out = isinstance(error, McpError) and error.error.code == 408
            if request.root.method == "tools/call" and (
                isinstance(error, asyncio.CancelledError) or timed_out
            ):
                with anyio.move_on_after(0.25, shield=True):
                    try:
                        await self.send_notification(types.ClientNotification(
                            types.CancelledNotification(
                                method="notifications/cancelled",
                                params=types.CancelledNotificationParams(
                                    requestId=request_id, reason="Request cancelled",
                                ),
                            )
                        ))
                    except Exception:
                        log.warning("mcpCancellationFailure=CONNECTION_CLOSED")
            raise


def startup_code(error: BaseException) -> McpErrorCode:
    """Reduce nested SDK task-group failures to explicitly allowed categories."""
    if isinstance(error, BaseExceptionGroup):
        codes = [startup_code(item) for item in error.exceptions]
        return next((code for code in codes if code != McpErrorCode.START_FAILED),
                    McpErrorCode.START_FAILED)
    if isinstance(error, McpCallError):
        return error.code
    if isinstance(error, TimeoutError):
        return McpErrorCode.TIMEOUT
    if isinstance(error, ValueError):
        known = {
            "MCP_TOOL_CATALOG_CHANGED": McpErrorCode.CATALOG_CHANGED,
            "ADMISSION_CATALOG_CHANGED": McpErrorCode.CATALOG_CHANGED,
            "MCP_TOOL_SCHEMA_CHANGED": McpErrorCode.SCHEMA_CHANGED,
            "ADMISSION_SCHEMA_CHANGED": McpErrorCode.SCHEMA_CHANGED,
        }
        return known.get(str(error), McpErrorCode.START_FAILED)
    return McpErrorCode.START_FAILED


class OwnedMcpClient:
    """One fixed stdio child, owned by its own task, with no automatic recovery."""

    def __init__(self, tool_name: str, call_timeout: float) -> None:
        """Initialize disconnected state; no I/O occurs during construction."""
        self.tool_name = tool_name
        self.call_timeout = call_timeout
        self.startup_timeout = 10.0
        self.status = McpStatus(True, McpState.CLOSED)
        self.session: CancellingClientSession | None = None
        self._owner: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._stopping = False
        self._active: set[asyncio.Task[types.CallToolResult]] = set()

    def server_parameters(self) -> StdioServerParameters:
        """Return the fixed child entrypoint and explicitly permitted config."""
        raise NotImplementedError

    def stderr_path(self) -> str:
        """Discard peer stderr by default; explicit diagnostic clients may capture it."""
        return os.devnull

    @staticmethod
    def validate_tools(discovered: types.ListToolsResult) -> None:
        """Reject tools or schemas beyond this client's fixed domain contract."""
        raise NotImplementedError

    def _disconnected(self) -> None:
        if not self._stopping and self.status.state != McpState.UNAVAILABLE:
            was_ready = self.status.state == McpState.READY
            self.status.state = McpState.UNAVAILABLE
            self.status.error_code = McpErrorCode.CONNECTION_CLOSED
            if was_ready:
                log.warning("mcpLifecycle tool=%s state=UNAVAILABLE code=CONNECTION_CLOSED", self.tool_name)
        self.session = None
        self._wake.set()

    async def _cancel_calls(self) -> None:
        pending = list(self._active)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _own(self, initialized: asyncio.Event) -> None:
        try:
            async with AsyncExitStack() as stack:
                errors = stack.enter_context(open(self.stderr_path(), "w", encoding="utf-8"))
                async with asyncio.timeout(self.startup_timeout):
                    reader, writer = await stack.enter_async_context(
                        stdio_client(self.server_parameters(), errlog=errors)
                    )
                    session = CancellingClientSession(reader, writer)
                    session.on_disconnect(self._disconnected)
                    await stack.enter_async_context(session)
                    await session.initialize()
                    self.validate_tools(await session.list_tools())
                    if self._wake.is_set():
                        raise McpCallError(McpErrorCode.CONNECTION_CLOSED)
                self.session = session
                self.status.state = McpState.READY
                self.status.error_code = None
                initialized.set()
                try:
                    await self._wake.wait()
                finally:
                    self.session = None
                    await self._cancel_calls()
                    if self._stopping:
                        # send_notification waits for the stdio writer's queue,
                        # not necessarily its OS write. A ping round trip drains
                        # prior cancellation notifications before closing pipes.
                        with anyio.move_on_after(0.5, shield=True):
                            try:
                                await session.send_ping()
                            except Exception:
                                log.warning("mcpShutdownDrain tool=%s outcome=UNAVAILABLE", self.tool_name)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self._stopping:
                self.status.state = McpState.UNAVAILABLE
                self.status.error_code = (
                    startup_code(error) if not initialized.is_set()
                    else McpErrorCode.CONNECTION_CLOSED
                )
                log.warning("mcpLifecycle tool=%s state=UNAVAILABLE code=%s",
                            self.tool_name, self.status.error_code.value)
        finally:
            self.session = None
            if not self._stopping and self.status.state == McpState.READY:
                self._disconnected()
            initialized.set()

    @asynccontextmanager
    async def connect(self, *, isolate_failure: bool = False) -> AsyncIterator[None]:
        """Run context entry/exit in one owner task; optionally isolate startup failure."""
        if self._owner is not None:
            raise McpCallError(McpErrorCode.START_FAILED)
        # SDK logs may contain untrusted payloads; only project categories escape.
        sdk_log = logging.getLogger("mcp")
        if not any(isinstance(handler, logging.NullHandler) for handler in sdk_log.handlers):
            sdk_log.addHandler(logging.NullHandler())
        sdk_log.propagate = False
        root_log = logging.getLogger()
        if not any(isinstance(item, SafeSdkDiagnostics) for item in root_log.filters):
            root_log.addFilter(SafeSdkDiagnostics())
        self.status.state = McpState.STARTING
        initialized = asyncio.Event()
        self._owner = asyncio.create_task(
            self._own(initialized), name=f"mcp-owner-{self.tool_name}"
        )
        try:
            await initialized.wait()
            if self.status.state != McpState.READY and not isolate_failure:
                raise McpCallError(self.status.error_code or McpErrorCode.START_FAILED)
            yield
        finally:
            starting = self.status.state == McpState.STARTING
            self._stopping = True
            self.status.state = McpState.CLOSED
            self.session = None
            self._wake.set()
            if starting:
                self._owner.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(self._owner, return_exceptions=True)

    async def invoke(
        self,
        parameters: dict[str, object],
        budget: CallBudget | None,
        decode: Callable[[object], DecodedT],
    ) -> DecodedT:
        """Submit one counted attempt, validate its result and log safe metadata."""
        call_id = uuid4().hex
        started = monotonic()
        outcome = "SUCCESS"
        task: asyncio.Task[types.CallToolResult] | None = None
        try:
            session = self.session
            if session is None or self.status.state != McpState.READY:
                raise McpCallError(self.status.error_code or McpErrorCode.CONNECTION_CLOSED)
            if budget is not None:
                try:
                    budget.consume()
                except RuntimeError:
                    raise McpCallError(McpErrorCode.CALL_LIMIT) from None
            task = asyncio.create_task(session.call_tool(self.tool_name, parameters))
            self._active.add(task)
            async with asyncio.timeout(self.call_timeout):
                result = await task
            if result.isError:
                raise McpCallError(McpErrorCode.TOOL_FAILED)
            if result.structuredContent is None:
                raise McpCallError(McpErrorCode.RESULT_INVALID)
            try:
                return decode(result.structuredContent)
            except (ValueError, TypeError, KeyError):
                raise McpCallError(McpErrorCode.RESULT_INVALID) from None
        except asyncio.CancelledError:
            if not self._stopping and self.status.state == McpState.UNAVAILABLE:
                outcome = McpErrorCode.CONNECTION_CLOSED.value
                raise McpCallError(McpErrorCode.CONNECTION_CLOSED) from None
            outcome = "CANCELLED"
            raise
        except TimeoutError:
            outcome = McpErrorCode.TIMEOUT.value
            raise McpCallError(McpErrorCode.TIMEOUT) from None
        except McpCallError as error:
            outcome = error.code.value
            raise
        except McpError as error:
            code = McpErrorCode.TOOL_FAILED
            if error.error.code == CONNECTION_CLOSED:
                code = McpErrorCode.CONNECTION_CLOSED
                self._disconnected()
            elif error.error.code == 408:
                code = McpErrorCode.TIMEOUT
            outcome = code.value
            raise McpCallError(code) from None
        except (anyio.BrokenResourceError, anyio.ClosedResourceError, EOFError, OSError):
            outcome = McpErrorCode.CONNECTION_CLOSED.value
            self._disconnected()
            raise McpCallError(McpErrorCode.CONNECTION_CLOSED) from None
        except ValueError:
            outcome = McpErrorCode.RESULT_INVALID.value
            raise McpCallError(McpErrorCode.RESULT_INVALID) from None
        except Exception:
            outcome = McpErrorCode.INTERNAL_ERROR.value
            raise McpCallError(McpErrorCode.INTERNAL_ERROR) from None
        finally:
            if task is not None:
                self._active.discard(task)
            log.info("mcpCall id=%s tool=%s outcome=%s elapsedMs=%d budgetUsed=%d budgetLimit=%d",
                     call_id, self.tool_name, outcome, int((monotonic() - started) * 1000),
                     budget.used if budget else 0, budget.limit if budget else 0)
