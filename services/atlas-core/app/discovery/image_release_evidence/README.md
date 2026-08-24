# Reviewed Image-Release Evidence (v0.14 P1b)

This directory is the reviewed and accepted evidence root for the inert
v0.14 P1b image-release evidence loader
(`app/discovery/image_release_evidence_loader.py`).

## Reviewed evidence publication

Checking in a row is an acceptance and publication boundary. Human review does
not change its provenance: `curated` and `registry_attested` remain distinct
source classes, and a reviewed `registry_attested` row must not be rewritten as
`curated`. Every `registry_attested` row requires separately reviewed,
reproducible cryptographic proof.

The runtime loader only parses and validates these local published files. It
performs no network or cryptographic verification. No production code path
reads this directory at runtime, and no evidence row grants deployment, update,
pull, restart, or any other operational authority.

## Schema

Each evidence file is one YAML document with exactly two keys:

```yaml
schema_version: 1
evidence:
  catalog_item_id: my-service
  release_version: "1.2.3"
  image_reference: ghcr.example/atlas/my-service
  image_digest: sha256:0000000000000000000000000000000000000000000000000000000000000000
  source_class: curated   # curated | registry_attested | upstream_signed
  source_id: some-source-identifier
  attested_at: "2026-08-01T00:00:00Z"
```

- `schema_version` is strictly `Literal[1]`; any other value fails the load.
- `evidence` must be exactly one existing `ImageReleaseEvidence` row
  (frozen, extra-forbid). Row validation is delegated entirely to the
  existing P1a `ImageReleaseEvidence` validators in
  `app/discovery/models.py`; P1b adds no row-level rules.

## Duplicate/conflict semantics

The loader fails the **entire** load on any violation; it never returns
partial results:

- **Duplicate `source_id` across files always fails**
  (`ImageReleaseEvidenceDuplicateError`). `source_id` is a globally
  unique provenance identifier.
- **Agreement is retained:** rows with the same
  `catalog_item_id` + `release_version` + `image_reference` +
  `image_digest` but **different** `source_id` are allowed. Both
  provenances are retained in the loaded result (independent
  attestations of the same fact).
- **Conflict fails** (`ImageReleaseEvidenceConflictError`): rows for
  the same `catalog_item_id` + `release_version` whose
  `image_reference` or `image_digest` differs.
- **Different item/version pairs never conflict.**
- All semantics are deterministic regardless of file discovery or
  creation order: files are read in POSIX path order and agreement is a
  symmetric relation, so swapping file order yields the same result.

## P1b scope: offline, inert, no consumer

- P1b is **offline and contract-only**: the loader performs local
  filesystem reads only. It has **no network, registry (OCI/GHCR),
  GitHub, credential, clock, subprocess, cache, or write behavior**.
- P1b has **no production consumer**: the loader is unexported
  (`app/discovery/__init__.py` is intentionally untouched) and nothing
  in the application imports it.
- Evidence publication does not activate a collector or adapter. Any runtime
  collection remains separately reviewed and out of scope.
