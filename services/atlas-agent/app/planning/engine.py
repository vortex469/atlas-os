"""Deterministic roadmap planning engine."""

from collections.abc import Iterable
from pathlib import Path

from app.planning.exceptions import PlanningValidationError
from app.planning.models import (
    ImplementationPlan,
    PlanRisk,
    RoadmapCheckpoint,
)
from app.repository.models import RepositorySnapshot


class PlanningEngine:
    """Create validated plans without Git, filesystem, or LLM operations."""

    def plan(
        self,
        checkpoint: RoadmapCheckpoint,
        snapshot: RepositorySnapshot,
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
        risks = self._deduplicate((*explicit_risks, *repository_risks))

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
    def _deduplicate[T](values: Iterable[T]) -> tuple[T, ...]:
        unique: list[T] = []

        for value in values:
            if value not in unique:
                unique.append(value)

        return tuple(unique)
