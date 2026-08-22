# Discovery Center API Contract

Discovery Center exposes a read-only, provider-neutral catalog and compatibility API under `/api/v1/discovery`.

This document describes the implemented discovery center contract (post-D7 era). It does not describe future Orion recommendations, Atlas Agent execution, catalog editing, semantic search, dynamic ingestion, or install workflows.

## Guarantees

- All Discovery routes are read-only `GET` routes.
- Responses use public API DTOs, not internal domain models.
- Search is deterministic and local.
- Compatibility is deterministic and evidence-based.
- Numeric compatibility scores are not exposed.
- Unknown environment facts produce `insufficient_information`, not success or warning.
- Errors are sanitized and do not expose filesystem paths, YAML filenames, parser traces, secrets, or runtime-private data.
- Catalog inclusion does not imply compatibility, support, installability, or approval to execute changes.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/discovery` | Read Discovery subsystem status. |
| `GET` | `/api/v1/discovery/items` | Browse catalog entries. |
| `GET` | `/api/v1/discovery/items/{item_id}` | Read one catalog entry. |
| `GET` | `/api/v1/discovery/items/{item_id}/evidence` | Read curated and supplemental dynamic evidence for one catalog entry. |
| `GET` | `/api/v1/discovery/items/{item_id}/relationships` | Read direct incoming and outgoing relationships. |
| `GET` | `/api/v1/discovery/items/{item_id}/compatibility` | Read deterministic compatibility for one item. |
| `GET` | `/api/v1/discovery/search` | Search catalog entries deterministically. |

There are no Discovery write endpoints.

## Status endpoint

`GET /api/v1/discovery`

Response fields:

- `catalog_loaded`: whether the catalog loaded successfully.
- `entry_count`: number of loaded catalog entries.
- `schema_version`: current catalog schema version.

An empty catalog is valid and is not an error.

## Browse endpoint

`GET /api/v1/discovery/items`

Supported query parameters:

- `type`: repeatable item type filter. Values use Discovery item type enum values.
- `status`: repeatable item status filter.
- `tag`: repeatable tag filter. All supplied tags must match.
- `capability`: repeatable capability filter. All supplied capabilities must match.
- `relationship_type`: repeatable relationship type filter. Any supplied type may match.
- `relationship_target`: repeatable relationship target filter. Any supplied target may match.
- `limit`: page size, minimum `1`, maximum `100`, default `50`.
- `offset`: zero-based offset, default `0`.

Ordering semantics:

1. deterministic catalog ordering
2. filtering
3. pagination

Response fields:

- `entries`: catalog entry DTOs.
- `total`: total matches before pagination.
- `limit`: effective limit.
- `offset`: effective offset.
- `has_more`: whether another page exists.

## Item endpoint

`GET /api/v1/discovery/items/{item_id}`

Returns one catalog entry DTO.

Catalog entry fields:

- `schema_version`
- `item`
- `provenance`
- `metadata`

Item fields include id, type, status, name, description, aliases, tags, URLs, capabilities, requirements, relationships, and approved public metadata.

## Evidence endpoint

`GET /api/v1/discovery/items/{item_id}/evidence`

This is a `GET`-only endpoint. It accepts no request body and no query parameters. The response model is `DiscoveryMergedItemProjection`, with schema version `discovery-merged-item-v1`.

The additive, read-only `release_evaluation` property on this projection was
added in Atlas v0.13 (Compatibility/Upgrade Intelligence). It is absent or
`null` when it cannot be computed and never changes the curated result;
publication and the `atlas-v0.13.0` tag remain pending.

Response fields:

- `schema_version`: `discovery-merged-item-v1`.
- `catalog_item_id`: the mapped catalog item identifier.
- `curated`: the authoritative curated catalog entry.
- `dynamic_claims`: supplemental, non-authoritative release claims. Each claim includes `fact_kind`, `version`, `published_at`, `freshness`, and bounded `provenance`.
- `source_states`: bounded evidence state for each mapped dynamic source. Each state includes `source_id`, `health`, and `cache_state`.
- `conflict_state`: `none`, `agreement`, `dynamic_conflict`, or `curated_conflict`.
- `release_evaluation`: an additive, optional, read-only upgrade-intelligence
  projection. It is absent or `null` when it cannot be computed and never
  changes the curated result. When present it includes:
  - `status`: one of the eight bounded release-evaluation statuses below.
  - `baseline`: the authoritative baseline version, or `null`. Each baseline has
    `version` (the authoritative version, preserved as provided) and
    `source`, which is exactly `curated` or `item_version`.
  - `latest_candidate`: the freshest strict numeric `X.Y.Z` dynamic release
    version selected, or `null` when none is selected. Positive statuses
    (`up_to_date`, `update_available`, `baseline_ahead`) always carry it, and
    `conflicted` always has it `null`. It may also be reported informationally
    for `insufficient_information` when a fresh strict candidate was selected
    but the baseline is non-comparable.
  - `reason`: a bounded, controlled reason for the state, or `null` for the
    positive statuses.

Release-evaluation statuses (exactly these eight):

- `no_baseline`: no authoritative baseline version is available to compare.
- `no_dynamic_evidence`: no dynamic release claims are available to compare
  against the baseline.
- `insufficient_information`: the available versions cannot be compared as
  strict numeric `X.Y.Z` versions.
- `stale_evidence`: the latest dynamic release evidence is stale and may not
  describe the current upstream release. No positive comparison is made.
- `conflicted`: release claims conflict, so no latest version is selected. The
  curated catalog remains authoritative.
- `up_to_date`: the freshest dynamic release evidence matches the authoritative
  baseline version.
- `update_available`: a newer upstream release is observed than the
  authoritative baseline version.
- `baseline_ahead`: the authoritative baseline version is ahead of the freshest
  observed upstream release.

Baseline precedence: the baseline is the curated release version when present
(`baseline.source=curated`), otherwise the item version
(`baseline.source=item_version`). A conflict always resolves to `conflicted`
with `latest_candidate` `null`, taking precedence over `no_baseline`. Only
strict numeric `X.Y.Z` versions are comparable; a missing or non-strict
baseline or candidate yields `insufficient_information` and never a positive
status.

The curated catalog item remains authoritative; dynamic claims supplement it and do not override it. Claim `freshness` is `fresh` or `stale`. Stale claims remain visible, while expired claims are omitted. Source `health` may be `healthy`, `degraded`, `unavailable`, or `null`; it is `null` until the process has observed that source. Source `cache_state` is `absent`, `available`, or `corrupt`.

The endpoint only reads existing state. A `GET` performs no network request or refresh and does not initialize, publish, or repair a cache. Cache absence does not prevent the curated response. A corrupt or unreadable cache is bounded as `corrupt` and degrades to curated-only evidence.

An unknown or unmapped item returns a sanitized `404` without selecting or reading a dynamic source. An invalid request clock or unexpected internal projection failure returns a bounded, sanitized `500` response.

This projection introduces no mutation or execution authority.

Production refresh is an explicit startup boundary controlled by
`ATLAS_ENABLE_DISCOVERY_DYNAMIC_REFRESH`, which defaults to `false`. When it is
enabled, Core initializes only the rebuildable Discovery cache and performs one
bounded refresh of the fixed Frigate GitHub release source. Source or network
failure records degraded/unavailable health and preserves curated-only reads.
Rejected cache initialization is likewise bounded at activation, records the
fixed source as unavailable, and lets Core continue without repairing or
rewriting the cache.
The evidence `GET` never initiates that refresh.

## Search endpoint

`GET /api/v1/discovery/search`

Required query parameter:

- `q`: search text, minimum length `1`, maximum length `200`.

Search also supports the same filters and pagination parameters as browse.

Ordering semantics:

1. deterministic ranking
2. filtering
3. pagination

Search responses include evidence explaining matched fields, matched text, and match type. Internal numeric scores are not exposed.

## Relationship endpoint

`GET /api/v1/discovery/items/{item_id}/relationships`

Optional query parameter:

- `type`: relationship type filter.

Response fields:

- `item_id`
- `incoming`: direct incoming relationships.
- `outgoing`: direct outgoing relationships.

Each relationship reference includes:

- `source_item_id`
- `target`
- `relationship`
- `resolved_target_item_id`
- `resolved`

Relationship results are direct only. Recursive traversal, transitive dependency expansion, cycle detection, and execution planning are not part of this API.

## Compatibility endpoint

`GET /api/v1/discovery/items/{item_id}/compatibility`

Optional query parameter:

- `target`: compatibility target identifier, default `atlas`.

Response fields:

- `item_id`
- `target_id`
- `target_type`
- `status`
- `checked_at`
- `findings`
- `evidence`
- `unknown_facts`

Implemented compatibility statuses:

- `compatible`
- `compatible_with_warnings`
- `insufficient_information`
- `incompatible`

Compatibility is evidence-based. Findings reference evidence by ID through `evidence_ids`. Evidence is returned once in the assessment-level `evidence` collection.

Unknown facts are never interpreted as compatible and are never treated as warnings. Known missing requirements produce incompatible findings.

Version-bounds compatibility: when a required relationship declares a curated
`minimum_version` and/or `maximum_version`, the observed installed version of
the resolved service is compared as a strict numeric `X.Y.Z` value. A version
below the minimum or above the maximum is `incompatible`; a satisfying version
is `compatible`; a missing or non-strict-numeric version is
`insufficient_information`. Observed installed versions are advisory evidence,
not authority, and version-bounds checks add no execution or remediation
authority.

## Error semantics

Common public errors:

- `404`: requested Discovery item does not exist.
- `422`: invalid query parameters or duplicate filter values.
- `503`: catalog or compatibility context is unavailable.

Detailed loader, repository, parser, path, and validation internals are logged server-side and sanitized from public responses.

## Non-goals

Discovery API does not:

- Install packages.
- Create, start, stop, or modify containers.
- Modify provider configuration.
- Write policies, runtime config, or secrets.
- Open ports.
- Generate Orion recommendations.
- Execute Atlas Agent handoffs.
- Perform semantic search.
- Ingest dynamic catalog data.
- Edit catalog entries.
