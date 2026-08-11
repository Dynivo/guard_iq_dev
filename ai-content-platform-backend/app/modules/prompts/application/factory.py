"""Compose Prompt Builder stack."""

from __future__ import annotations

from pathlib import Path

from app.modules.ai_cache.application.namespaced import NamespacedAICache, PromptCache
from app.modules.ai_cache.infrastructure.memory_cache import InMemoryAICache
from app.modules.prompts.application.analytics import PromptAnalytics
from app.modules.prompts.application.benchmarks import DefaultPromptBenchmarkRunner
from app.modules.prompts.application.builder import DefaultPromptBuilder
from app.modules.prompts.application.compiler import DefaultPromptCompiler
from app.modules.prompts.application.diff import DefaultPromptDiffer
from app.modules.prompts.application.evaluator import DefaultPromptEvaluator
from app.modules.prompts.application.linter import DefaultPromptLinter
from app.modules.prompts.application.optimizer import DefaultPromptOptimizer
from app.modules.prompts.application.policy_engine import DefaultPromptPolicyEngine
from app.modules.prompts.application.security_scanner import DefaultPromptSecurityScanner
from app.modules.prompts.application.validator import DefaultPromptValidator
from app.modules.prompts.infrastructure.memory_replay import InMemoryPromptReplayStore
from app.modules.prompts.infrastructure.policy_loader import YamlPromptPolicyLoader
from app.modules.prompts.infrastructure.schema_registry import YamlOutputSchemaRegistry
from app.modules.prompts.infrastructure.yaml_registry import YamlPromptRegistry

_PROMPTS = Path(__file__).resolve().parents[4] / "configs" / "prompts"


class PromptBuilderFactory:
    @staticmethod
    def create_memory(
        *,
        prompts_dir: Path | None = None,
        analytics: PromptAnalytics | None = None,
        policy_id: str = "default",
    ) -> DefaultPromptBuilder:
        root = prompts_dir or _PROMPTS
        partials = root / "partials"
        registry = YamlPromptRegistry(root)
        compiler = DefaultPromptCompiler(partials)
        cache = PromptCache(NamespacedAICache(InMemoryAICache()))
        policy_loader = YamlPromptPolicyLoader(root / "policies")
        return DefaultPromptBuilder(
            registry=registry,
            compiler=compiler,
            optimizer=DefaultPromptOptimizer(),
            validator=DefaultPromptValidator(),
            schema_registry=YamlOutputSchemaRegistry(root / "schemas"),
            replay_store=InMemoryPromptReplayStore(),
            prompt_cache=cache,
            analytics=analytics or PromptAnalytics(),
            linter=DefaultPromptLinter(partials),
            security_scanner=DefaultPromptSecurityScanner(partials),
            policy_engine=DefaultPromptPolicyEngine(policy_loader),
            partials_dir=partials,
            policy_id=policy_id,
        )

    @staticmethod
    def create_components(
        *, prompts_dir: Path | None = None, policy_id: str = "default"
    ) -> dict:
        root = prompts_dir or _PROMPTS
        partials = root / "partials"
        analytics = PromptAnalytics()
        registry = YamlPromptRegistry(root)
        compiler = DefaultPromptCompiler(partials)
        optimizer = DefaultPromptOptimizer()
        validator = DefaultPromptValidator()
        schemas = YamlOutputSchemaRegistry(root / "schemas")
        replay = InMemoryPromptReplayStore()
        cache = PromptCache(NamespacedAICache(InMemoryAICache()))
        linter = DefaultPromptLinter(partials)
        security = DefaultPromptSecurityScanner(partials)
        policy_loader = YamlPromptPolicyLoader(root / "policies")
        policy_engine = DefaultPromptPolicyEngine(policy_loader)
        builder = DefaultPromptBuilder(
            registry=registry,
            compiler=compiler,
            optimizer=optimizer,
            validator=validator,
            schema_registry=schemas,
            replay_store=replay,
            prompt_cache=cache,
            analytics=analytics,
            linter=linter,
            security_scanner=security,
            policy_engine=policy_engine,
            partials_dir=partials,
            policy_id=policy_id,
        )
        return {
            "builder": builder,
            "registry": registry,
            "compiler": compiler,
            "optimizer": optimizer,
            "validator": validator,
            "schemas": schemas,
            "evaluator": DefaultPromptEvaluator(),
            "differ": DefaultPromptDiffer(),
            "replay": replay,
            "analytics": analytics,
            "linter": linter,
            "security": security,
            "policy_engine": policy_engine,
            "policy_loader": policy_loader,
            "benchmarks": DefaultPromptBenchmarkRunner(root / "benchmarks"),
        }
