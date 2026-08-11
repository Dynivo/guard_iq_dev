"""WorkflowFactory — compose a ready-to-run engine with builtins."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.infrastructure.events.factory import get_event_bus
from app.modules.workflow.application.builtin_handlers import register_builtin_handlers
from app.modules.workflow.application.engine import DefaultWorkflowEngine
from app.modules.workflow.domain.ports import ExecutionHistoryStore
from app.modules.workflow.infrastructure.history_memory import InMemoryExecutionHistoryStore
from app.modules.workflow.infrastructure.metrics_memory import InMemoryWorkflowMetrics
from app.modules.workflow.infrastructure.node_registry import InMemoryNodeRegistry
from app.modules.workflow.infrastructure.registry import InMemoryWorkflowRegistry
from app.modules.workflow.infrastructure.yaml_loader import YamlWorkflowLoader


class WorkflowFactory:
    """Build engine + registries; optionally load all YAML from a directory.

    YAML is loaded once at create time — the run path never re-reads disk.
    Use ``CachedWorkflowRegistry`` when invalidate/reload is required.
    """

    @staticmethod
    def create(
        *,
        workflows_dir: Path | None = None,
        load_builtins: bool = True,
        history: ExecutionHistoryStore | None = None,
        middlewares: list[Any] | None = None,
        interceptors: list[Any] | None = None,
    ) -> tuple[DefaultWorkflowEngine, InMemoryWorkflowRegistry, InMemoryNodeRegistry]:
        workflow_registry = InMemoryWorkflowRegistry()
        node_registry = InMemoryNodeRegistry()
        if load_builtins:
            register_builtin_handlers(node_registry)
            from app.modules.knowledge.application.handlers import register_knowledge_handlers
            from app.modules.content.application.handlers import register_content_handlers
            from app.modules.prompts.application.handlers import register_prompt_handlers
            from app.modules.news.application.handlers import register_news_handlers
            from app.modules.image.application.handlers import register_image_handlers
            from app.modules.typography.application.handlers import register_typography_handlers
            from app.modules.carousel.application.handlers import register_carousel_handlers
            from app.modules.review.application.handlers import register_review_handlers
            from app.modules.learning.application.handlers import (
                register_learning_workflow_handlers,
            )
            from app.modules.analytics.application.handlers import (
                register_analytics_workflow_handlers,
            )
            from app.modules.consensus.application.handlers import (
                register_consensus_workflow_handlers,
            )

            register_knowledge_handlers(node_registry)
            register_content_handlers(node_registry)
            register_prompt_handlers(node_registry)
            register_news_handlers(node_registry)
            register_image_handlers(node_registry)
            register_typography_handlers(node_registry)
            register_carousel_handlers(node_registry)
            register_review_handlers(node_registry)
            register_learning_workflow_handlers(node_registry)
            register_analytics_workflow_handlers(node_registry)
            register_consensus_workflow_handlers(node_registry)

        if workflows_dir is not None and workflows_dir.is_dir():
            loader = YamlWorkflowLoader()
            for definition in loader.load_dir(workflows_dir):
                workflow_registry.register(definition)

        engine = DefaultWorkflowEngine(
            workflow_registry=workflow_registry,
            node_registry=node_registry,
            event_bus=get_event_bus(),
            metrics=InMemoryWorkflowMetrics(),
            history=history or InMemoryExecutionHistoryStore(),
            middlewares=middlewares,
            interceptors=interceptors,
        )
        return engine, workflow_registry, node_registry
