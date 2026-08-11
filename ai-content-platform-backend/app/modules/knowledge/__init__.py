"""Knowledge Engine module."""

from app.modules.knowledge.domain.models import KnowledgeQuery, OptimizedContext

__all__ = ["KnowledgeQuery", "OptimizedContext", "KnowledgeEngineFactory"]


def __getattr__(name: str):
    if name == "KnowledgeEngineFactory":
        from app.modules.knowledge.application.factory import KnowledgeEngineFactory

        return KnowledgeEngineFactory
    raise AttributeError(name)
