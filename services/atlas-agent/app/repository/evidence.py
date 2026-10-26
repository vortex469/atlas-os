"""Canonical, request-bound facts retained from an exact repository review."""

import json
import re
from hashlib import sha256
from pathlib import Path

from app.repository.models import CommitRequest, ReviewedChangeEvidence

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def reviewed_evidence_fingerprint(evidence: ReviewedChangeEvidence) -> str:
    """Preserve the released version-2 digest format byte for byte."""

    manifest = {
        "version": 2,
        "repository_root": str(evidence.repository_root),
        "expected_branch": evidence.expected_branch,
        "expected_head": evidence.expected_head,
        "reviewed_files": [str(path) for path in evidence.reviewed_files],
        "commit_message": evidence.commit_message,
        "changes": [
            {
                "path": str(change.path),
                "status": change.status,
                "content_sha256": change.content_sha256,
                "git_mode": change.git_mode,
                "deletion_marker": change.deletion_marker,
                "rename_source": str(change.rename_source)
                if change.rename_source is not None
                else None,
            }
            for change in evidence.changes
        ],
    }
    return sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _safe_relative(path: Path) -> bool:
    return (
        isinstance(path, Path)
        and not path.is_absolute()
        and bool(path.parts)
        and path != Path(".")
        and ".." not in path.parts
        and "\0" not in str(path)
    )


def validate_reviewed_evidence(
    evidence: ReviewedChangeEvidence,
    request: CommitRequest | None,
    fingerprint: str | None,
) -> None:
    """Refuse mismatched or malformed saved facts without reading the checkout."""

    if not isinstance(evidence, ReviewedChangeEvidence) or request is None:
        raise ValueError("Reviewed facts require an exact commit request")
    paths = evidence.reviewed_files
    if not (
        paths
        and all(_safe_relative(path) for path in paths)
        and paths == tuple(sorted(set(paths))) == tuple(sorted(request.paths))
        and evidence.repository_root == request.repository_root
        and evidence.expected_branch == request.expected_branch
        and evidence.expected_head == request.expected_head
        and evidence.commit_message == request.message
        and tuple(change.path for change in evidence.changes) == paths
    ):
        raise ValueError("Reviewed facts do not match the commit request")
    for change in evidence.changes:
        if not (
            isinstance(change.status, str)
            and len(change.status) == 2
            and change.status != "  "
            and set(change.status) <= set(" MTADRCU?!")
            and (change.rename_source is None or _safe_relative(change.rename_source))
        ):
            raise ValueError("Reviewed file facts are malformed")
        if change.deletion_marker == "deleted":
            valid = change.content_sha256 is None and change.git_mode is None
        else:
            valid = (
                change.deletion_marker is None
                and change.git_mode in {"100644", "100755"}
                and isinstance(change.content_sha256, str)
                and _DIGEST.fullmatch(change.content_sha256) is not None
            )
        if not valid:
            raise ValueError("Reviewed file facts are malformed")
    if not (
        isinstance(fingerprint, str)
        and _DIGEST.fullmatch(fingerprint)
        and evidence.fingerprint
        == fingerprint
        == reviewed_evidence_fingerprint(evidence)
    ):
        raise ValueError("Reviewed facts do not match the approved fingerprint")
