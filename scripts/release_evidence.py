"""Collect bounded, read-only Atlas release evidence."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

try:
    from atlas_data_recovery_evidence import (
        EvidenceStatus as RecoveryStatus,
    )
    from atlas_data_recovery_evidence import (
        load_recovery_evidence,
    )
except ModuleNotFoundError:
    from scripts.atlas_data_recovery_evidence import (
        EvidenceStatus as RecoveryStatus,
    )
    from scripts.atlas_data_recovery_evidence import (
        load_recovery_evidence,
    )

SCHEMA_VERSION = "atlas-release-evidence-v1"
ALLOWED_UNTRACKED = ("compose.execution-smoke.override.yaml",)
EXPECTED_TUPLES = ("restart-service/proxmox/qemu",)
MAX_PATHS = 100
MAX_RUNS = 10
MAX_IMAGES = 20
MAX_TEXT = 256
REQUIRED_WORKFLOWS = ("Quality gates", "Container release gate")


class CheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    ABSENT = "absent"
    NOT_EVALUATED = "not_evaluated"
    PATH_FILTERED = "path_filtered"
    NOT_REQUIRED = "not_required"


class SummaryState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class ReadOnlyRunner:
    """Execute only explicitly recognized read-only command shapes."""

    _TOOLS = frozenset({"git", "gh", "docker", "bash"})
    _FORBIDDEN = frozenset(
        {
            "commit", "push", "tag", "merge", "create", "edit", "delete",
            "release", "up", "down", "restart", "start", "stop", "kill",
            "rm", "apply", "exec",
        }
    )

    def available(self, tool: str) -> bool:
        return tool in self._TOOLS and shutil.which(tool) is not None

    def run(self, argv: Sequence[str], *, cwd: Path) -> CommandResult:
        values = tuple(argv)
        tool = Path(values[0]).name if values else ""
        if not values or (
            values[0] not in self._TOOLS and tool != "operational-capability-parity"
        ):
            raise ValueError("release evidence command is not allow-listed")
        if any(value.lower() in self._FORBIDDEN for value in values[1:]):
            raise ValueError("mutating release evidence command is prohibited")
        if not _is_read_only_command(values):
            raise ValueError("release evidence command shape is not allow-listed")
        completed = subprocess.run(
            values,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _is_read_only_command(argv: tuple[str, ...]) -> bool:
    if Path(argv[0]).name == "operational-capability-parity":
        return len(argv) == 1
    if argv[0] == "git":
        return len(argv) > 1 and argv[1] in {
            "rev-parse", "status", "rev-list", "merge-base", "cat-file",
            "ls-files", "diff", "grep",
        }
    if argv[0] == "gh":
        return len(argv) > 2 and argv[1:3] == ("run", "list")
    if argv[0] == "docker":
        return len(argv) > 1 and (
            argv[1] == "inspect"
            or (argv[1] == "compose" and "config" in argv and "ps" not in argv)
            or (argv[1] == "compose" and "ps" in argv and "-q" in argv)
        )
    if argv[0] == "bash":
        return len(argv) >= 3 and argv[1] == "-n"
    return False


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    branch: str | None
    head_sha: str | None
    origin_main_sha: str | None
    expected_sha: str | None
    requested_tag: str | None
    tag_object_sha: str | None
    peeled_commit_sha: str | None
    head_matches_expected: bool | None
    main_matches_head: bool | None
    tag_matches_head: bool | None
    base_is_ancestor: bool | None
    commits_ahead_of_main: int | None
    commits_behind_main: int | None


@dataclass(frozen=True, slots=True)
class WorktreeEvidence:
    tracked_clean: bool
    allowed_untracked_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    paths_truncated: bool


@dataclass(frozen=True, slots=True)
class WorkflowRunEvidence:
    workflow: str
    run_id: int | None
    event: str | None
    branch: str | None
    commit_sha: str | None
    status: CheckState
    conclusion: str | None


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    status: CheckState
    production_tuples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComposeEvidence:
    base_render: CheckState
    hardened_render: CheckState
    atlas_edge_host_published: bool | None
    mission_control_host_published: bool | None
    controlled_reason: str | None


@dataclass(frozen=True, slots=True)
class ImageEvidence:
    status: CheckState
    source_parity_status: CheckState
    service_images: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class SecretFinding:
    path: str
    category: str


@dataclass(frozen=True, slots=True)
class SecurityEvidence:
    status: CheckState
    findings: tuple[SecretFinding, ...]
    findings_truncated: bool


@dataclass(frozen=True, slots=True)
class ValidationEvidence:
    diff_check: CheckState
    shell_syntax: CheckState
    container_gate: CheckState


@dataclass(frozen=True, slots=True)
class RecoveryAcceptanceEvidence:
    status: CheckState
    schema_version: str | None
    tested_commit_sha: str | None
    controlled_reason: str | None


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    status: SummaryState
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    schema_version: str
    release_identity: ReleaseIdentity
    worktree: WorktreeEvidence
    capability: CapabilityEvidence
    ci: tuple[WorkflowRunEvidence, ...]
    deployment: ComposeEvidence
    images: ImageEvidence
    security: SecurityEvidence
    validation: ValidationEvidence
    recovery: RecoveryAcceptanceEvidence
    summary: EvidenceSummary


@dataclass(frozen=True, slots=True)
class Options:
    expected_base: str
    candidate_tag: str | None
    expected_sha: str | None
    require_main: bool
    require_tag: bool
    check_running_images: bool
    recovery_evidence: Path | None = None


def collect_evidence(root: Path, options: Options, runner: ReadOnlyRunner) -> ReleaseEvidence:
    identity, identity_states = _release_identity(root, options, runner)
    worktree = _worktree(root, runner)
    capability = _capability(root, runner)
    ci = _ci(root, identity.head_sha, runner)
    compose = _compose(root, runner)
    images = _images(root, runner) if options.check_running_images else ImageEvidence(
        CheckState.NOT_EVALUATED, CheckState.NOT_EVALUATED, (), False
    )
    security = _security(root, runner)
    validation = _validation(root, runner)
    recovery = _recovery(options.recovery_evidence, identity.head_sha)
    blocked: list[str] = list(identity_states)
    incomplete: list[str] = []
    if not worktree.tracked_clean:
        blocked.append("tracked_worktree_not_clean")
    if worktree.unexpected_paths:
        blocked.append("unexpected_worktree_paths")
    if capability.status is CheckState.FAILED:
        blocked.append("capability_parity_failed")
    for run in ci:
        if run.status is CheckState.FAILED:
            blocked.append(f"ci_failed:{run.workflow}")
        elif run.status in {CheckState.PENDING, CheckState.ABSENT, CheckState.NOT_EVALUATED}:
            incomplete.append(f"ci_incomplete:{run.workflow}")
    if compose.base_render is CheckState.FAILED or compose.hardened_render is CheckState.FAILED:
        blocked.append("compose_or_ingress_failed")
    elif compose.base_render is CheckState.NOT_EVALUATED or compose.hardened_render is CheckState.NOT_EVALUATED:
        incomplete.append("compose_evidence_unavailable")
    if images.status is CheckState.FAILED:
        blocked.append("running_image_inspection_failed")
    elif options.check_running_images and images.status is CheckState.NOT_EVALUATED:
        incomplete.append("running_image_evidence_unavailable")
    if security.status is CheckState.FAILED:
        blocked.append("tracked_private_material_found")
    if validation.diff_check is CheckState.FAILED or validation.shell_syntax is CheckState.FAILED:
        blocked.append("local_validation_failed")
    if recovery.status is CheckState.FAILED:
        blocked.append("recovery_evidence_failed")
    if blocked:
        summary = EvidenceSummary(SummaryState.BLOCKED, tuple(sorted(set(blocked))))
    elif incomplete:
        summary = EvidenceSummary(SummaryState.INCOMPLETE, tuple(sorted(set(incomplete))))
    else:
        summary = EvidenceSummary(SummaryState.READY, ())
    return ReleaseEvidence(
        SCHEMA_VERSION, identity, worktree, capability, ci, compose, images,
        security, validation, recovery, summary,
    )


def _recovery(
    path: Path | None,
    head_sha: str | None,
) -> RecoveryAcceptanceEvidence:
    if path is None:
        return RecoveryAcceptanceEvidence(
            CheckState.NOT_EVALUATED, None, None, "not_requested"
        )
    if head_sha is None:
        return RecoveryAcceptanceEvidence(
            CheckState.FAILED, None, None, "candidate_sha_unavailable"
        )
    try:
        evidence = load_recovery_evidence(path, expected_commit_sha=head_sha)
    except (TypeError, ValueError):
        return RecoveryAcceptanceEvidence(
            CheckState.FAILED, None, None, "invalid_or_mismatched_evidence"
        )
    return RecoveryAcceptanceEvidence(
        CheckState.PASSED
        if evidence.status is RecoveryStatus.READY
        else CheckState.FAILED,
        evidence.schema_version,
        evidence.tested_commit_sha,
        None if evidence.status is RecoveryStatus.READY else "not_ready",
    )


def _release_identity(
    root: Path, options: Options, runner: ReadOnlyRunner
) -> tuple[ReleaseIdentity, tuple[str, ...]]:
    branch = _git_value(runner, root, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git_value(runner, root, "rev-parse", "HEAD")
    main = _git_value(runner, root, "rev-parse", "origin/main")
    tag_object = peeled = None
    if options.candidate_tag:
        raw = _git_value(runner, root, "rev-parse", options.candidate_tag)
        peeled = _git_value(runner, root, "rev-parse", f"{options.candidate_tag}^{{commit}}")
        kind = _git_value(runner, root, "cat-file", "-t", options.candidate_tag)
        tag_object = raw if kind == "tag" else None
    base_check = runner.run(
        ("git", "merge-base", "--is-ancestor", options.expected_base, "HEAD"), cwd=root
    )
    ahead = _git_count(runner, root, "origin/main..HEAD")
    behind = _git_count(runner, root, "HEAD..origin/main")
    reasons: list[str] = []
    if options.expected_sha and head != options.expected_sha:
        reasons.append("head_sha_mismatch")
    if options.require_main and head != main:
        reasons.append("origin_main_sha_mismatch")
    if options.require_tag and not options.candidate_tag:
        reasons.append("required_tag_not_supplied")
    if options.require_tag and peeled is None:
        reasons.append("required_tag_not_found")
    if options.require_tag and peeled is not None and peeled != head:
        reasons.append("tag_commit_mismatch")
    if base_check.returncode != 0:
        reasons.append("expected_base_not_ancestor")
    return ReleaseIdentity(
        branch, head, main, options.expected_sha, options.candidate_tag,
        tag_object, peeled,
        head == options.expected_sha if options.expected_sha and head else None,
        head == main if head and main else None,
        peeled == head if peeled and head else None,
        base_check.returncode == 0,
        ahead,
        behind,
    ), tuple(reasons)


def _worktree(root: Path, runner: ReadOnlyRunner) -> WorktreeEvidence:
    result = runner.run(("git", "status", "--porcelain=v1", "-z"), cwd=root)
    tracked: list[str] = []
    allowed: list[str] = []
    unexpected: list[str] = []
    for record in result.stdout.split("\0"):
        if not record:
            continue
        code, path = record[:2], record[3:]
        if code == "??":
            (allowed if path in ALLOWED_UNTRACKED else unexpected).append(path)
        else:
            tracked.append(path)
    combined = sorted((*tracked, *unexpected))
    return WorktreeEvidence(
        tracked_clean=not tracked,
        allowed_untracked_paths=tuple(sorted(allowed)[:MAX_PATHS]),
        unexpected_paths=tuple(combined[:MAX_PATHS]),
        paths_truncated=len(combined) > MAX_PATHS,
    )


def _capability(root: Path, runner: ReadOnlyRunner) -> CapabilityEvidence:
    completed = runner.run(
        (str(root / "scripts/operational-capability-parity"),), cwd=root
    )
    status = CheckState.PASSED if completed.returncode == 0 else CheckState.FAILED
    return CapabilityEvidence(status, EXPECTED_TUPLES if status is CheckState.PASSED else ())


def _ci(root: Path, head: str | None, runner: ReadOnlyRunner) -> tuple[WorkflowRunEvidence, ...]:
    if head is None or not runner.available("gh"):
        return tuple(
            WorkflowRunEvidence(name, None, None, None, head, CheckState.NOT_EVALUATED, None)
            for name in REQUIRED_WORKFLOWS
        )
    evidence: list[WorkflowRunEvidence] = []
    for name in REQUIRED_WORKFLOWS:
        result = runner.run(
            (
                "gh", "run", "list", "--workflow", name, "--commit", head,
                "--limit", str(MAX_RUNS), "--json",
                "databaseId,event,headBranch,headSha,status,conclusion,workflowName",
            ),
            cwd=root,
        )
        if result.returncode != 0:
            evidence.append(WorkflowRunEvidence(name, None, None, None, head, CheckState.NOT_EVALUATED, None))
            continue
        try:
            runs = json.loads(result.stdout)
        except json.JSONDecodeError:
            runs = []
        exact = [item for item in runs[:MAX_RUNS] if item.get("headSha") == head]
        evidence.append(_select_run(name, head, exact))
    return tuple(evidence)


def _select_run(name: str, head: str, runs: list[dict[str, object]]) -> WorkflowRunEvidence:
    if not runs:
        return WorkflowRunEvidence(name, None, None, None, head, CheckState.ABSENT, None)
    run = runs[0]
    conclusion = str(run.get("conclusion") or "") or None
    status_value = str(run.get("status") or "")
    state = (
        CheckState.PASSED if conclusion == "success"
        else CheckState.PENDING if status_value != "completed" or not conclusion
        else CheckState.FAILED
    )
    return WorkflowRunEvidence(
        name,
        int(run["databaseId"]) if isinstance(run.get("databaseId"), int) else None,
        _bounded(run.get("event")),
        _bounded(run.get("headBranch")),
        _bounded(run.get("headSha")),
        state,
        _bounded(conclusion),
    )


def _compose(root: Path, runner: ReadOnlyRunner) -> ComposeEvidence:
    if not runner.available("docker"):
        return ComposeEvidence(CheckState.NOT_EVALUATED, CheckState.NOT_EVALUATED, None, None, "docker_unavailable")
    base = runner.run(
        ("docker", "compose", "-f", "compose.production.yaml", "config", "--format", "json"),
        cwd=root,
    )
    hardened = runner.run(
        (
            "docker", "compose", "-f", "compose.production.yaml",
            "-f", "compose.https.yaml", "-f", "compose.operator-auth.yaml",
            "config", "--format", "json",
        ),
        cwd=root,
    )
    if base.returncode != 0 or hardened.returncode != 0:
        return ComposeEvidence(
            CheckState.PASSED if base.returncode == 0 else CheckState.NOT_EVALUATED,
            CheckState.NOT_EVALUATED,
            None, None, "required_compose_inputs_unavailable",
        )
    try:
        rendered = json.loads(hardened.stdout)
        services = rendered["services"]
        edge = bool(services.get("atlas-edge", {}).get("ports"))
        mission = bool(services.get("mission-control", {}).get("ports"))
    except (KeyError, TypeError, json.JSONDecodeError):
        return ComposeEvidence(CheckState.PASSED, CheckState.FAILED, None, None, "invalid_compose_projection")
    hardened_state = CheckState.PASSED if edge and not mission else CheckState.FAILED
    return ComposeEvidence(CheckState.PASSED, hardened_state, edge, mission, None)


def _images(root: Path, runner: ReadOnlyRunner) -> ImageEvidence:
    if not runner.available("docker"):
        return ImageEvidence(CheckState.NOT_EVALUATED, CheckState.NOT_EVALUATED, (), False)
    result = runner.run(
        ("docker", "compose", "-f", "compose.production.yaml", "ps", "-q"), cwd=root
    )
    identifiers = tuple(value for value in result.stdout.splitlines() if value)[:MAX_IMAGES]
    if result.returncode != 0 or not identifiers:
        return ImageEvidence(CheckState.NOT_EVALUATED, CheckState.NOT_EVALUATED, (), False)
    inspected = runner.run(
        ("docker", "inspect", "--format", "{{.Name}}={{.Image}}", *identifiers), cwd=root
    )
    if inspected.returncode != 0:
        return ImageEvidence(CheckState.FAILED, CheckState.NOT_EVALUATED, (), False)
    values = tuple(sorted(_bounded(value) or "" for value in inspected.stdout.splitlines()))
    return ImageEvidence(
        CheckState.PASSED,
        CheckState.NOT_EVALUATED,
        values[:MAX_IMAGES],
        len(values) > MAX_IMAGES,
    )


def _security(root: Path, runner: ReadOnlyRunner) -> SecurityEvidence:
    result = runner.run(("git", "ls-files", "-z"), cwd=root)
    findings: list[SecretFinding] = []
    for path in result.stdout.split("\0"):
        lowered = path.lower()
        category = None
        if lowered.startswith("secrets/"):
            category = "tracked_secrets_path"
        elif lowered.endswith((".key", ".pem")) and "example" not in lowered:
            category = "tls_private_material_path"
        elif "htpasswd" in lowered and "example" not in lowered:
            category = "htpasswd_path"
        elif "operator" in lowered and "verifier" in lowered and "test" not in lowered:
            category = "operator_verifier_path"
        elif lowered.endswith(".env") and "example" not in lowered:
            category = "release_sensitive_env_path"
        if category:
            findings.append(SecretFinding(_bounded(path) or "", category))
    content_checks = (
        ("-----BEGIN [A-Z ]*PRIVATE KEY-----", "private_key_material"),
        (r"\$argon2(id|i|d)\$", "operator_verifier_material"),
    )
    for pattern, category in content_checks:
        matches = runner.run(
            (
                "git", "grep", "-Il", "-E", pattern, "--", ".",
                ":(exclude)**/tests/**", ":(exclude)**/test*/**",
                ":(exclude)**/*.example",
            ),
            cwd=root,
        )
        if matches.returncode not in {0, 1}:
            continue
        for path in matches.stdout.splitlines():
            if _is_test_fixture(path):
                continue
            findings.append(SecretFinding(_bounded(path) or "", category))
    findings = sorted(findings, key=lambda item: (item.category, item.path))
    return SecurityEvidence(
        CheckState.FAILED if findings else CheckState.PASSED,
        tuple(findings[:MAX_PATHS]),
        len(findings) > MAX_PATHS,
    )


def _validation(root: Path, runner: ReadOnlyRunner) -> ValidationEvidence:
    diff = runner.run(("git", "diff", "--check"), cwd=root)
    shell_results = [
        runner.run(("bash", "-n", path), cwd=root).returncode
        for path in ("scripts/container-release-gate", "scripts/release-evidence")
    ]
    return ValidationEvidence(
        CheckState.PASSED if diff.returncode == 0 else CheckState.FAILED,
        CheckState.PASSED if all(code == 0 for code in shell_results) else CheckState.FAILED,
        CheckState.NOT_EVALUATED,
    )


def _git_value(runner: ReadOnlyRunner, root: Path, *args: str) -> str | None:
    result = runner.run(("git", *args), cwd=root)
    return _bounded(result.stdout.strip()) if result.returncode == 0 else None


def _git_count(runner: ReadOnlyRunner, root: Path, revision: str) -> int | None:
    value = _git_value(runner, root, "rev-list", "--count", revision)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _bounded(value: object) -> str | None:
    if value is None:
        return None
    return str(value)[:MAX_TEXT]


def _is_test_fixture(path: str) -> bool:
    parts = Path(path).parts
    return "tests" in parts or any(part.startswith("test_") for part in parts)


class EvidenceArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = EvidenceArgumentParser(description="Collect read-only Atlas release evidence.")
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--candidate-tag")
    parser.add_argument("--expected-sha")
    parser.add_argument("--require-main", action="store_true")
    parser.add_argument("--require-tag", action="store_true")
    parser.add_argument("--check-running-images", action="store_true")
    parser.add_argument("--recovery-evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        root = Path(__file__).resolve().parent.parent
        evidence = collect_evidence(
            root,
            Options(
                args.expected_base, args.candidate_tag, args.expected_sha,
                args.require_main, args.require_tag, args.check_running_images,
                args.recovery_evidence,
            ),
            ReadOnlyRunner(),
        )
    except (OSError, ValueError) as error:
        print(f"release evidence configuration error: {type(error).__name__}", file=sys.stderr)
        return 3
    payload = asdict(evidence)
    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(f"Atlas release evidence: {evidence.summary.status}")
        print(f"HEAD: {evidence.release_identity.head_sha or 'unavailable'}")
        print(f"origin/main: {evidence.release_identity.origin_main_sha or 'unavailable'}")
        print(f"capability: {evidence.capability.status}")
        print(f"recovery: {evidence.recovery.status}")
        for run in evidence.ci:
            print(f"CI {run.workflow}: {run.status} run={run.run_id or 'unavailable'}")
        for reason in evidence.summary.reasons:
            print(f"reason: {reason}")
    return exit_code(evidence.summary.status)


def exit_code(status: SummaryState) -> int:
    """Map the controlled summary state to the documented process status."""

    return {
        SummaryState.READY: 0,
        SummaryState.BLOCKED: 1,
        SummaryState.INCOMPLETE: 2,
    }[status]


if __name__ == "__main__":
    raise SystemExit(main())
