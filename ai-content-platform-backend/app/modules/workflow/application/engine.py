"""Default WorkflowEngine — domain-agnostic orchestration."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.core.observability import ensure_correlation_id, set_correlation_id
from app.modules.workflow.application.conditions import DefaultConditionEvaluator
from app.modules.workflow.application.fallback import resolve_fallback
from app.modules.workflow.application.interceptors import InterceptorRegistry
from app.modules.workflow.application.middleware import MiddlewareChain
from app.modules.workflow.application.node_executor import RegistryNodeExecutor
from app.modules.workflow.application.retry import should_retry, sleep_before_retry
from app.modules.workflow.application.validator import DefaultWorkflowValidator
from app.modules.workflow.domain.models import (
    CancelToken,
    ExecutionHistoryRecord,
    NodeOutcome,
    SimulationOptions,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowNode,
    WorkflowResult,
)
from app.modules.workflow.domain.ports import (
    ConditionEvaluator,
    ExecutionHistoryStore,
    NodeExecutor,
    NodeRegistry,
    WorkflowMetricsPort,
    WorkflowRegistry,
    WorkflowValidator,
)
from app.shared.events.ports import EventBus
from app.shared.result import Failure

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DefaultWorkflowEngine:
    def __init__(
        self,
        *,
        workflow_registry: WorkflowRegistry,
        node_registry: NodeRegistry,
        event_bus: EventBus,
        metrics: WorkflowMetricsPort,
        history: ExecutionHistoryStore,
        validator: WorkflowValidator | None = None,
        conditions: ConditionEvaluator | None = None,
        node_executor: NodeExecutor | None = None,
        middlewares: list[Any] | None = None,
        interceptors: InterceptorRegistry | list[Any] | None = None,
        max_steps: int = 10_000,
    ) -> None:
        self._workflows = workflow_registry
        self._nodes = node_registry
        self._bus = event_bus
        self._metrics = metrics
        self._history = history
        self._validator = validator or DefaultWorkflowValidator()
        self._conditions = conditions or DefaultConditionEvaluator()
        self._default_executor = node_executor or RegistryNodeExecutor(node_registry)
        self._middleware = MiddlewareChain(middlewares)
        if isinstance(interceptors, InterceptorRegistry):
            self._interceptors = interceptors
        else:
            self._interceptors = InterceptorRegistry()
            for item in interceptors or []:
                self._interceptors.register(item)
        self._max_steps = max_steps

    async def run(
        self,
        workflow_name: str,
        *,
        initial_context: WorkflowContext,
        version: str | None = None,
        cancel_token: CancelToken | None = None,
        simulation: SimulationOptions | None = None,
        workflow_timeout_ms: int | None = None,
    ) -> WorkflowResult:
        try:
            definition = self._workflows.get(workflow_name, version)
        except KeyError as exc:
            return WorkflowResult(
                success=False,
                execution_id=initial_context.execution_id,
                workflow_name=workflow_name,
                workflow_version=version or "",
                context=initial_context,
                error_code="UNKNOWN_WORKFLOW",
                error_message=str(exc),
            )
        validation = self._validator.validate(definition, self._nodes.known_types())
        if isinstance(validation, Failure):
            return WorkflowResult(
                success=False,
                execution_id=initial_context.execution_id,
                workflow_name=workflow_name,
                workflow_version=definition.version if definition else "",
                context=initial_context,
                error_code=validation.code,
                error_message=validation.message,
            )

        definition = validation.value
        timeout_ms = (
            workflow_timeout_ms if workflow_timeout_ms is not None else definition.timeout_ms
        )
        body = self._run_validated(
            definition,
            initial_context,
            cancel_token=cancel_token,
            simulation=simulation,
        )
        if timeout_ms and timeout_ms > 0:
            try:
                return await asyncio.wait_for(body, timeout=timeout_ms / 1000.0)
            except TimeoutError:
                context = initial_context
                context.workflow_name = definition.name
                context.workflow_version = definition.version
                execution = WorkflowExecution(
                    execution_id=context.execution_id,
                    workflow_name=definition.name,
                    workflow_version=definition.version,
                    status="failed",
                    started_at=_utcnow(),
                )
                await self._emit(
                    "WorkflowTimedOut",
                    context,
                    {"timeout_ms": timeout_ms},
                )
                return await self._finish(
                    execution,
                    context,
                    time.perf_counter(),
                    success=False,
                    cancelled=False,
                    code="TIMEOUT",
                    message=f"Workflow timed out after {timeout_ms}ms",
                )
        return await body

    async def _run_validated(
        self,
        definition: WorkflowDefinition,
        initial_context: WorkflowContext,
        *,
        cancel_token: CancelToken | None,
        simulation: SimulationOptions | None,
    ) -> WorkflowResult:
        context = initial_context
        context.workflow_name = definition.name
        context.workflow_version = definition.version
        if simulation is not None:
            context.state["simulation"] = True
        if not context.correlation_id:
            context.correlation_id = ensure_correlation_id()
        else:
            set_correlation_id(context.correlation_id)
        if not context.request_id:
            context.request_id = context.correlation_id

        if simulation is not None and isinstance(self._default_executor, RegistryNodeExecutor):
            executor: NodeExecutor = self._default_executor.with_simulation(simulation)
        elif simulation is not None:
            executor = RegistryNodeExecutor(self._nodes, simulation=simulation)
        else:
            executor = self._default_executor

        execution = WorkflowExecution(
            execution_id=context.execution_id,
            workflow_name=definition.name,
            workflow_version=definition.version,
            status="running",
            started_at=_utcnow(),
            current_node_id=definition.entry_node_id,
        )
        started = time.perf_counter()
        self._metrics.record_workflow_started(execution.execution_id, definition.name)
        await self._middleware.before_workflow(context, definition.name)
        await self._interceptors.before_workflow(context, definition.name)
        await self._emit(
            "WorkflowStarted",
            context,
            {"workflow_name": definition.name, "workflow_version": definition.version},
        )
        await self._history.append(
            ExecutionHistoryRecord(
                execution_id=execution.execution_id,
                event="WorkflowStarted",
                timestamp=_utcnow(),
                detail={"workflow_name": definition.name},
            )
        )

        node_id: str | None = definition.entry_node_id
        steps = 0
        result: WorkflowResult | None = None

        try:
            while node_id is not None:
                if cancel_token is not None and cancel_token.is_cancelled:
                    result = await self._finish(
                        execution,
                        context,
                        started,
                        success=False,
                        cancelled=True,
                        code="CANCELLED",
                        message=cancel_token.reason or "Workflow cancelled",
                    )
                    break

                steps += 1
                if steps > self._max_steps:
                    result = await self._fail(
                        execution,
                        context,
                        started,
                        code="MAX_STEPS",
                        message="Workflow exceeded maximum step count",
                    )
                    break

                node = definition.get_node(node_id)
                if node is None:
                    result = await self._fail(
                        execution,
                        context,
                        started,
                        code="MISSING_NODE",
                        message=f"Node '{node_id}' not found",
                    )
                    break

                execution.current_node_id = node.id
                context.clear_node_scope()
                outcome, _retries = await self._execute_node(
                    node,
                    context,
                    execution,
                    executor=executor,
                    cancel_token=cancel_token,
                )

                if outcome.cancelled:
                    result = await self._finish(
                        execution,
                        context,
                        started,
                        success=False,
                        cancelled=True,
                        code="CANCELLED",
                        message="Workflow cancelled",
                    )
                    break

                if outcome.timed_out:
                    await self._emit(
                        "NodeTimedOut",
                        context,
                        {"node_id": node.id, "timeout_ms": node.timeout_ms},
                    )
                    result = await self._fail(
                        execution,
                        context,
                        started,
                        code="TIMEOUT",
                        message=outcome.error_message or f"Node '{node.id}' timed out",
                    )
                    break

                if outcome.success:
                    context.update(outcome.outputs)
                    if node.terminal or not node.conditions:
                        break
                    node_id = self._next_node(node, context, last_success=True)
                    if node_id is None:
                        result = await self._fail(
                            execution,
                            context,
                            started,
                            code="NO_TRANSITION",
                            message=f"No matching transition from node '{node.id}'",
                        )
                        break
                    continue

                context.add_error(
                    node_id=node.id,
                    message=outcome.error_message or "node failed",
                )
                decision = resolve_fallback(node)
                if decision.action == "stop":
                    result = await self._fail(
                        execution,
                        context,
                        started,
                        code="NODE_FAILED",
                        message=outcome.error_message or f"Node '{node.id}' failed",
                    )
                    break
                if decision.action == "skip":
                    if node.terminal or not node.conditions:
                        break
                    node_id = self._next_node(node, context, last_success=True)
                    continue
                if decision.action == "continue_node":
                    node_id = decision.next_node_id
                    continue
                result = await self._fail(
                    execution,
                    context,
                    started,
                    code="FALLBACK_ERROR",
                    message="Unresolved fallback",
                )
                break

            if result is None:
                result = await self._finish(
                    execution,
                    context,
                    started,
                    success=True,
                    cancelled=False,
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "workflow.engine_error",
                extra={
                    "app_module": "workflow",
                    "operation": "run",
                    "correlation_id": context.correlation_id,
                    "outcome": "failure",
                },
            )
            result = await self._fail(
                execution,
                context,
                started,
                code="ENGINE_ERROR",
                message=str(exc),
            )

        await self._middleware.after_workflow(context, result)
        await self._interceptors.after_workflow(context, result)
        return result

    async def _execute_node(
        self,
        node: WorkflowNode,
        context: WorkflowContext,
        execution: WorkflowExecution,
        *,
        executor: NodeExecutor,
        cancel_token: CancelToken | None,
    ) -> tuple[NodeOutcome, int]:
        attempts = 0
        max_attempts = max(1, node.retry.max_attempts)
        last_outcome = NodeOutcome(success=False, error_message="not executed")
        node_started = time.perf_counter()

        await self._middleware.before_node(context, node)
        await self._interceptors.before_node(context, node)
        await self._emit(
            "NodeStarted",
            context,
            {"node_id": node.id, "node_type": node.type, "node_name": node.name},
        )
        await self._history.append(
            ExecutionHistoryRecord(
                execution_id=execution.execution_id,
                event="NodeStarted",
                timestamp=_utcnow(),
                node_id=node.id,
            )
        )

        while attempts < max_attempts:
            if cancel_token is not None and cancel_token.is_cancelled:
                last_outcome = NodeOutcome(
                    success=False,
                    cancelled=True,
                    error_message=cancel_token.reason or "cancelled",
                )
                break
            attempts += 1
            execution.attempt_counts[node.id] = attempts
            try:
                last_outcome = await executor.execute(node, context)
            except Exception as exc:  # noqa: BLE001
                last_outcome = NodeOutcome(success=False, error_message=str(exc))

            if last_outcome.success or last_outcome.cancelled or last_outcome.timed_out:
                break
            if should_retry(node.retry, attempts):
                await sleep_before_retry(node.retry, attempts)
                continue
            break

        retries = max(0, attempts - 1)
        duration_ms = int((time.perf_counter() - node_started) * 1000)
        outcome_label = "success" if last_outcome.success else "failure"
        self._metrics.record_node_timing(
            execution.execution_id,
            node.id,
            duration_ms,
            retries,
            outcome_label,
        )

        await self._middleware.after_node(context, node, last_outcome)
        await self._interceptors.after_node(context, node, last_outcome)

        if last_outcome.success:
            await self._emit(
                "NodeCompleted",
                context,
                {"node_id": node.id, "retries": retries, "duration_ms": duration_ms},
            )
            await self._history.append(
                ExecutionHistoryRecord(
                    execution_id=execution.execution_id,
                    event="NodeCompleted",
                    timestamp=_utcnow(),
                    node_id=node.id,
                    detail={"retries": retries, "duration_ms": duration_ms},
                )
            )
        else:
            await self._emit(
                "NodeFailed",
                context,
                {
                    "node_id": node.id,
                    "retries": retries,
                    "error": last_outcome.error_message,
                    "timed_out": last_outcome.timed_out,
                },
            )
            await self._history.append(
                ExecutionHistoryRecord(
                    execution_id=execution.execution_id,
                    event="NodeFailed",
                    timestamp=_utcnow(),
                    node_id=node.id,
                    detail={
                        "error": last_outcome.error_message,
                        "retries": retries,
                        "timed_out": last_outcome.timed_out,
                    },
                )
            )

        return last_outcome, retries

    def _next_node(
        self,
        node: WorkflowNode,
        context: WorkflowContext,
        *,
        last_success: bool,
    ) -> str | None:
        for condition in node.conditions:
            if self._conditions.matches(condition, context, last_success=last_success):
                return condition.target_node_id
        return None

    async def _fail(
        self,
        execution: WorkflowExecution,
        context: WorkflowContext,
        started: float,
        *,
        code: str,
        message: str,
    ) -> WorkflowResult:
        return await self._finish(
            execution,
            context,
            started,
            success=False,
            cancelled=False,
            code=code,
            message=message,
        )

    async def _finish(
        self,
        execution: WorkflowExecution,
        context: WorkflowContext,
        started: float,
        *,
        success: bool,
        cancelled: bool,
        code: str | None = None,
        message: str | None = None,
    ) -> WorkflowResult:
        duration_ms = int((time.perf_counter() - started) * 1000)
        execution.finished_at = _utcnow()
        execution.status = (
            "cancelled" if cancelled else ("completed" if success else "failed")
        )
        outcome = (
            "cancelled" if cancelled else ("success" if success else "failure")
        )
        self._metrics.record_workflow_finished(
            execution.execution_id, outcome, duration_ms
        )
        event_type = (
            "WorkflowCancelled"
            if cancelled
            else ("WorkflowCompleted" if success else "WorkflowFailed")
        )
        await self._emit(
            event_type,
            context,
            {
                "duration_ms": duration_ms,
                "error_code": code,
                "error_message": message,
            },
        )
        await self._history.append(
            ExecutionHistoryRecord(
                execution_id=execution.execution_id,
                event=event_type,
                timestamp=_utcnow(),
                detail={"duration_ms": duration_ms, "code": code},
            )
        )
        return WorkflowResult(
            success=success and not cancelled,
            execution_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            workflow_version=execution.workflow_version,
            context=context,
            error_code=code,
            error_message=message,
            metrics_summary=self._metrics.summary(execution.execution_id),
            cancelled=cancelled,
        )

    async def _emit(
        self,
        event_type: str,
        context: WorkflowContext,
        payload: dict,
    ) -> None:
        from app.shared.events.types import DomainEvent

        org = context.organization_id or uuid.UUID(int=0)
        event = DomainEvent(
            event_type=event_type,
            organization_id=org,
            correlation_id=context.correlation_id,
            payload={
                "execution_id": context.execution_id,
                "workflow_name": context.workflow_name,
                "workflow_version": context.workflow_version,
                **payload,
            },
        )
        await self._bus.publish(event)
