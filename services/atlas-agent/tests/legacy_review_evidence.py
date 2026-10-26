"""Historical version-1 review digest for upgrade-compatibility fixtures only."""

import json
from hashlib import sha256

from app.repository.models import ReviewedChangeEvidence


def version_one_fingerprint(evidence: ReviewedChangeEvidence) -> str:
    # Keep the released v1 format, including its lack of a Git-mode field.
    manifest = {
        "version": 1,
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
                "deletion_marker": change.deletion_marker,
                "rename_source": str(change.rename_source) if change.rename_source is not None else None,
            }
            for change in evidence.changes
        ],
    }
    return sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
