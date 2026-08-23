# Curated Image-Release Evidence (v0.14 P1b)

This directory is the curated evidence root for the inert v0.14 P1b
image-release evidence loader
(`app/discovery/image_release_evidence_loader.py`).

## Shipped state: ZERO evidence rows

This directory ships with **zero** `.yaml` / `.yml` evidence rows. The
only file that ships here is this README. `ImageReleaseEvidenceLoader`
treats the default directory as an implicit default: an empty (or
missing) directory loads to an empty `LoadedImageReleaseEvidence`
result. No production code path reads this directory at runtime.

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
- A future **P1b-collector** (any component that produces new evidence
  rows, e.g. from registry attestation APIs) is **separately reviewed**
  and is not part of this change.
- Do **not** assume any registry authentication behavior and do **not**
  hard-code an authentication hostname in this contract or in future
  collector design.
- A future collector **must validate and constrain** any
  `WWW-Authenticate` challenge or endpoint it encounters under its own
  reviewed allowlist/security contract before any credential material
  is exposed to it.
