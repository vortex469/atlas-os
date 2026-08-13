"""Deterministic roadmap planning engine."""

from collections.abc import Iterable
from pathlib import Path

from app.context.models import AgentContext
from app.planning.exceptions import PlanningValidationError
from app.planning.models import (
    ImplementationPlan,
    PlanRisk,
    RoadmapCheckpoint,
)
from app.repository.models import RepositorySnapshot

_INTELLIGENCE_RISK_LIMIT = 5
_ACTION_HISTORY_RISK_LIMIT = 5
_QUALIFYING_INTELLIGENCE_STATES = frozenset(
    {
        "actionable",
        "concerning",
        "critical",
        "error",
        "failed",
        "high",
        "recommended",
        "unhealthy",
        "warning",
    }
)


class PlanningEngine:
    """Create validated plans without Git, filesystem, or LLM operations."""

    def plan(
        self,
        checkpoint: RoadmapCheckpoint,
        snapshot: RepositorySnapshot,
        context: AgentContext | None = None,
    ) -> ImplementationPlan:
        """Create an immutable implementation plan."""

        checkpoint_id = self._required_text(
            checkpoint.identifier,
            "identifier",
        )
        title = self._required_text(checkpoint.title, "title")
        goal = self._required_text(checkpoint.goal, "goal")

        scope_items = self._normalize_text_collection(
            checkpoint.scope_items,
            "scope item",
        )
        affected_files = self._normalize_paths(checkpoint.affected_files)
        required_tests = self._normalize_text_collection(
            checkpoint.required_tests,
            "required test",
        )

        explicit_risks = tuple(
            PlanRisk(
                code="checkpoint-risk",
                summary=summary,
                source="checkpoint",
            )
            for summary in self._normalize_text_collection(
                checkpoint.risks,
                "risk",
            )
        )

        repository_risks = self._repository_risks(snapshot)
        context_risks = self._context_risks(context)
        risks = self._deduplicate(
            (*explicit_risks, *repository_risks, *context_risks)
        )

        return ImplementationPlan(
            checkpoint_id=checkpoint_id,
            title=title,
            goal=goal,
            repository_root=snapshot.root,
            branch=snapshot.branch,
            head_commit=snapshot.head_commit,
            scope_items=scope_items,
            affected_files=affected_files,
            required_tests=required_tests,
            risks=risks,
        )

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise PlanningValidationError(
                f"Checkpoint {field_name} must not be blank"
            )
        return normalized

    def _normalize_text_collection(
        self,
        values: Iterable[str],
        item_name: str,
    ) -> tuple[str, ...]:
        normalized: list[str] = []

        for value in values:
            item = value.strip()
            if not item:
                raise PlanningValidationError(
                    f"Checkpoint {item_name} must not be blank"
                )
            normalized.append(item)

        return self._deduplicate(normalized)

    def _normalize_paths(
        self,
        values: Iterable[Path],
    ) -> tuple[Path, ...]:
        normalized: list[Path] = []

        for value in values:
            path = Path(value)

            if path.is_absolute():
                raise PlanningValidationError(
                    f"Affected file must be repository-relative: {path}"
                )

            if path == Path("."):
                raise PlanningValidationError(
                    "Affected file must identify a file path"
                )

            if ".." in path.parts:
                raise PlanningValidationError(
                    f"Affected file must not traverse parents: {path}"
                )

            normalized.append(path)

        return self._deduplicate(normalized)

    @staticmethod
    def _repository_risks(
        snapshot: RepositorySnapshot,
    ) -> tuple[PlanRisk, ...]:
        risks: list[PlanRisk] = []

        if not snapshot.is_clean:
            risks.append(
                PlanRisk(
                    code="dirty-working-tree",
                    summary=(
                        "Repository contains staged, modified, or "
                        "untracked files"
                    ),
                    source="repository",
                )
            )

        if snapshot.branch is None:
            risks.append(
                PlanRisk(
                    code="detached-head",
                    summary="Repository is not currently on a branch",
                    source="repository",
                )
            )

        if snapshot.head_commit is None:
            risks.append(
                PlanRisk(
                    code="missing-head",
                    summary="Repository does not have a HEAD commit",
                    source="repository",
                )
            )

        return tuple(risks)

    @staticmethod
    def _context_risks(
        context: AgentContext | None,
    ) -> tuple[PlanRisk, ...]:
        """Create deterministic risks from Atlas context."""

        if context is None:
            return ()

        risks: list[PlanRisk] = []

        for service_name, service in sorted(context.services.items()):
            if service.status == "healthy":
                continue

            risks.append(
                PlanRisk(
                    code="atlas-service-unhealthy",
                    summary=(
                        f"Atlas service '{service_name}' reports "
                        f"status '{service.status}'"
                    ),
                    source="atlas-core",
                )
            )

        intelligence = context.intelligence
        if intelligence is not None:
            risks.extend(PlanningEngine._intelligence_risks(intelligence))

        action_history = context.action_history
        if action_history is not None:
            if action_history.failure is not None:
                risks.append(
                    PlanRisk(
                        code="atlas-action-history-unavailable",
                        summary=action_history.failure.message,
                        source="atlas-knowledge",
                    )
                )
            else:
                risks.extend(
                    PlanningEngine._action_history_risks(action_history.entries)
                )
        return tuple(risks)

    @staticmethod
    def _intelligence_risks(intelligence) -> tuple[PlanRisk, ...]:
        if intelligence.failure is not None:
            return (
                PlanRisk(
                    code="atlas-intelligence-unavailable",
                    summary=intelligence.failure.message,
                    source="atlas-knowledge",
                ),
            )

        knowledge_risks: list[PlanRisk] = []
        evidence_keys: set[tuple[object, ...]] = set()

        for finding in intelligence.findings:
            if not (
                finding.affects_health
                or finding.severity.strip().lower()
                in _QUALIFYING_INTELLIGENCE_STATES
            ):
                continue
            key = (
                "finding",
                finding.identifier,
                finding.severity,
                finding.category,
                finding.source,
                finding.component,
            )
            PlanningEngine._append_intelligence_risk(
                risks=knowledge_risks,
                evidence_keys=evidence_keys,
                key=key,
                risk=PlanRisk(
                    code="atlas-intelligence-finding",
                    summary=finding.title,
                    source="atlas-knowledge",
                ),
            )
            if len(knowledge_risks) == _INTELLIGENCE_RISK_LIMIT:
                return tuple(knowledge_risks)

        for assessment in intelligence.assessments:
            if (
                assessment.priority.strip().lower()
                not in _QUALIFYING_INTELLIGENCE_STATES
            ):
                continue
            key = (
                "assessment",
                assessment.title,
                assessment.priority,
                assessment.component,
            )
            PlanningEngine._append_intelligence_risk(
                risks=knowledge_risks,
                evidence_keys=evidence_keys,
                key=key,
                risk=PlanRisk(
                    code="atlas-intelligence-assessment",
                    summary=assessment.title,
                    source="atlas-knowledge",
                ),
            )
            if len(knowledge_risks) == _INTELLIGENCE_RISK_LIMIT:
                return tuple(knowledge_risks)

        for recommendation in intelligence.recommendations:
            key = (
                "recommendation",
                recommendation.title,
                recommendation.reason,
                recommendation.priority,
                recommendation.component,
            )
            PlanningEngine._append_intelligence_risk(
                risks=knowledge_risks,
                evidence_keys=evidence_keys,
                key=key,
                risk=PlanRisk(
                    code="atlas-intelligence-recommendation",
                    summary=recommendation.title,
                    source="atlas-knowledge",
                ),
            )
            if len(knowledge_risks) == _INTELLIGENCE_RISK_LIMIT:
                break

        return tuple(knowledge_risks)

    @staticmethod
    def _action_history_risks(entries) -> tuple[PlanRisk, ...]:
        action_risks: list[PlanRisk] = []
        evidence_keys: set[tuple[object, ...]] = set()
        for entry in entries:
            if entry.status != "failed" and entry.success is not False:
                continue
            key = (
                entry.provider_id,
                entry.action_id,
                entry.status,
                entry.completed_at,
                entry.request_id or entry.identifier,
            )
            if key in evidence_keys:
                continue
            evidence_keys.add(key)
            action_risks.append(
                PlanRisk(
                    code="atlas-action-history-failure",
                    summary=(
                        f"Atlas provider action '{entry.action_label}' "
                        f"from '{entry.provider_name}' failed "
                        f"({entry.request_id or entry.identifier})"
                    ),
                    source="atlas-knowledge",
                )
            )
            if len(action_risks) == _ACTION_HISTORY_RISK_LIMIT:
                break
        return tuple(action_risks)

    @staticmethod
    def _append_intelligence_risk(
        *,
        risks: list[PlanRisk],
        evidence_keys: set[tuple[object, ...]],
        key: tuple[object, ...],
        risk: PlanRisk,
    ) -> None:
        if key in evidence_keys:
            return
        evidence_keys.add(key)
        risks.append(risk)

    @staticmethod
    def _deduplicate[T](values: Iterable[T]) -> tuple[T, ...]:
        unique: list[T] = []

        for value in values:
            if value not in unique:
                unique.append(value)

        return tuple(unique)
