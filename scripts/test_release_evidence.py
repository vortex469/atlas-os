"""Deterministic release-evidence collector tests."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from scripts.release_evidence import (
    MAX_PATHS,
    CheckState,
    CommandResult,
    Options,
    ReadOnlyRunner,
    SummaryState,
    _is_read_only_command,
    collect_evidence,
    exit_code,
    main,
)

HEAD = "a" * 40
MAIN = HEAD


class FakeRunner:
    def __init__(self) -> None:
        self.main = MAIN
        self.status = "?? compose.execution-smoke.override.yaml\0"
        self.tag_kind = "tag"
        self.tag_object = "b" * 40
        self.tag_commit = HEAD
        self.capability_code = 0
        self.gh_available = True
        self.docker_available = True
        self.ci: dict[str, list[dict[str, object]]] = {
            name: [
                {
                    "databaseId": index,
                    "event": "push",
                    "headBranch": "main",
                    "headSha": HEAD,
                    "status": "completed",
                    "conclusion": "success",
                    "workflowName": name,
                }
            ]
            for index, name in enumerate(
                ("Quality gates", "Container release gate"), start=100
            )
        }
        self.hardened = {
            "services": {
                "atlas-edge": {"ports": [{"published": "443"}]},
                "mission-control": {},
            }
        }
        self.tracked = "README.md\0"
        self.grep_paths: dict[str, str] = {}
        self.commands: list[tuple[str, ...]] = []

    def available(self, tool: str) -> bool:
        return (tool != "gh" or self.gh_available) and (
            tool != "docker" or self.docker_available
        )

    def run(self, argv, *, cwd):
        del cwd
        command = tuple(argv)
        self.commands.append(command)
        if command[:3] == ("git", "rev-parse", "--abbrev-ref"):
            return CommandResult(0, "feature/atlas-v0.9\n")
        if command == ("git", "rev-parse", "HEAD"):
            return CommandResult(0, f"{HEAD}\n")
        if command == ("git", "rev-parse", "origin/main"):
            return CommandResult(0, f"{self.main}\n")
        if command[:2] == ("git", "rev-parse") and command[-1].endswith("^{commit}"):
            return CommandResult(0, f"{self.tag_commit}\n")
        if command[:2] == ("git", "rev-parse"):
            return CommandResult(0, f"{self.tag_object}\n")
        if command[:2] == ("git", "cat-file"):
            return CommandResult(0, f"{self.tag_kind}\n")
        if command[:2] == ("git", "merge-base"):
            return CommandResult(0)
        if command[:3] == ("git", "rev-list", "--count"):
            return CommandResult(0, "0\n")
        if command[:2] == ("git", "status"):
            return CommandResult(0, self.status)
        if command[:2] == ("git", "ls-files"):
            return CommandResult(0, self.tracked)
        if command[:2] == ("git", "grep"):
            pattern = command[command.index("-E") + 1]
            output = self.grep_paths.get(pattern, "")
            return CommandResult(0 if output else 1, output)
        if command[:2] == ("git", "diff"):
            return CommandResult(0)
        if command[:2] == ("bash", "-n"):
            return CommandResult(0)
        if Path(command[0]).name == "operational-capability-parity":
            return CommandResult(
                self.capability_code,
                "Operational capability parity passed: restart-service/proxmox/qemu\n",
            )
        if command[:3] == ("gh", "run", "list"):
            name = command[command.index("--workflow") + 1]
            return CommandResult(0, json.dumps(self.ci[name]))
        if command[0:2] == ("docker", "compose") and "config" in command:
            rendered = self.hardened if "compose.https.yaml" in command else {"services": {}}
            return CommandResult(0, json.dumps(rendered))
        raise AssertionError(f"unexpected command: {command}")


def _options(**overrides) -> Options:
    values = {
        "expected_base": "atlas-v0.8.0",
        "candidate_tag": "atlas-v0.9-rc1",
        "expected_sha": HEAD,
        "require_main": True,
        "require_tag": True,
        "check_running_images": False,
    }
    values.update(overrides)
    return Options(**values)


def _collect(runner: FakeRunner, **options):
    return collect_evidence(Path("/repo"), _options(**options), runner)


def test_exact_sha_annotated_tag_main_and_allowed_override_are_ready() -> None:
    evidence = _collect(FakeRunner())

    assert evidence.summary.status is SummaryState.READY
    assert evidence.release_identity.head_matches_expected is True
    assert evidence.release_identity.tag_object_sha == "b" * 40
    assert evidence.release_identity.peeled_commit_sha == HEAD
    assert evidence.worktree.allowed_untracked_paths == (
        "compose.execution-smoke.override.yaml",
    )


def test_lightweight_tag_has_no_annotated_tag_object_and_still_peels() -> None:
    runner = FakeRunner()
    runner.tag_kind = "commit"
    runner.tag_object = HEAD

    evidence = _collect(runner)

    assert evidence.release_identity.tag_object_sha is None
    assert evidence.release_identity.peeled_commit_sha == HEAD
    assert evidence.release_identity.tag_matches_head is True


def test_wrong_origin_main_and_wrong_tag_commit_block() -> None:
    runner = FakeRunner()
    runner.main = "c" * 40
    runner.tag_commit = "d" * 40

    evidence = _collect(runner)

    assert evidence.summary.status is SummaryState.BLOCKED
    assert "origin_main_sha_mismatch" in evidence.summary.reasons
    assert "tag_commit_mismatch" in evidence.summary.reasons


@pytest.mark.parametrize(
    "status",
    [" M README.md\0", "?? unexpected.txt\0"],
)
def test_tracked_or_unexpected_worktree_state_blocks(status: str) -> None:
    runner = FakeRunner()
    runner.status = status

    evidence = _collect(runner)

    assert evidence.summary.status is SummaryState.BLOCKED


def test_capability_failure_blocks() -> None:
    runner = FakeRunner()
    runner.capability_code = 1

    evidence = _collect(runner)

    assert evidence.capability.status is CheckState.FAILED
    assert evidence.summary.status is SummaryState.BLOCKED


def test_ci_for_wrong_sha_is_absent_and_incomplete() -> None:
    runner = FakeRunner()
    runner.ci["Quality gates"][0]["headSha"] = "e" * 40

    evidence = _collect(runner)

    assert evidence.ci[0].status is CheckState.ABSENT
    assert evidence.summary.status is SummaryState.INCOMPLETE


def test_failed_ci_blocks_and_pending_ci_is_incomplete() -> None:
    failed = FakeRunner()
    failed.ci["Quality gates"][0]["conclusion"] = "failure"
    pending = FakeRunner()
    pending.ci["Quality gates"][0].update(status="in_progress", conclusion=None)

    assert _collect(failed).summary.status is SummaryState.BLOCKED
    assert _collect(pending).summary.status is SummaryState.INCOMPLETE


def test_missing_gh_is_controlled_incomplete() -> None:
    runner = FakeRunner()
    runner.gh_available = False

    evidence = _collect(runner)

    assert all(item.status is CheckState.NOT_EVALUATED for item in evidence.ci)
    assert evidence.summary.status is SummaryState.INCOMPLETE


def test_hardened_ingress_requires_edge_and_forbids_mission_control_port() -> None:
    passing = _collect(FakeRunner())
    failing_runner = FakeRunner()
    failing_runner.hardened["services"]["mission-control"] = {
        "ports": [{"published": "3000"}]
    }
    failing = _collect(failing_runner)

    assert passing.deployment.hardened_render is CheckState.PASSED
    assert failing.deployment.hardened_render is CheckState.FAILED
    assert failing.summary.status is SummaryState.BLOCKED


def test_secret_hygiene_reports_only_bounded_path_and_category() -> None:
    runner = FakeRunner()
    runner.tracked = "README.md\0secrets/operator.json\0"

    evidence = _collect(runner)

    assert evidence.security.status is CheckState.FAILED
    assert evidence.security.findings[0].path == "secrets/operator.json"
    assert evidence.security.findings[0].category == "tracked_secrets_path"
    assert "value" not in json.dumps(as_json(evidence.security))


def test_fake_secret_fixture_is_distinct_from_production_material() -> None:
    runner = FakeRunner()
    runner.grep_paths[r"\$argon2(id|i|d)\$"] = (
        "services/atlas-core/app/operator_auth/test_operator_auth.py\n"
        "config/operator-verifier.json\n"
    )

    evidence = _collect(runner)

    assert [item.path for item in evidence.security.findings] == [
        "config/operator-verifier.json"
    ]


def test_output_path_bounds_are_deterministic() -> None:
    runner = FakeRunner()
    runner.status = "".join(f"?? unexpected-{index}.txt\0" for index in range(MAX_PATHS + 5))

    evidence = _collect(runner)

    assert len(evidence.worktree.unexpected_paths) == MAX_PATHS
    assert evidence.worktree.paths_truncated is True


def test_read_only_allowlist_rejects_mutating_commands() -> None:
    for command in (
        ("git", "push"),
        ("git", "commit"),
        ("git", "tag", "v1"),
        ("gh", "pr", "merge"),
        ("docker", "compose", "up"),
        ("docker", "restart", "atlas-core"),
        ("curl", "-X", "POST", "https://example.invalid"),
    ):
        assert _is_read_only_command(command) is False

    with pytest.raises(ValueError):
        ReadOnlyRunner().run(("git", "push"), cwd=Path("/repo"))


def test_summary_states_map_to_documented_exit_codes() -> None:
    assert exit_code(SummaryState.READY) == 0
    assert exit_code(SummaryState.BLOCKED) == 1
    assert exit_code(SummaryState.INCOMPLETE) == 2
    assert main(("--unknown-option",)) == 3


def as_json(value):
    return asdict(value)
