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

Response fields:

- `schema_version`: `discovery-merged-item-v1`.
- `catalog_item_id`: the mapped catalog item identifier.
- `curated`: the authoritative curated catalog entry.
- `dynamic_claims`: supplemental, non-authoritative release claims. Each claim includes `fact_kind`, `version`, `published_at`, `freshness`, and bounded `provenance`.
- `source_states`: bounded evidence state for each mapped dynamic source. Each state includes `source_id`, `health`, and `cache_state`.
- `conflict_state`: `none`, `agreement`, `dynamic_conflict`, or `curated_conflict`.

The curated catalog item remains authoritative; dynamic claims supplement it and do not override it. Claim `freshness` is `fresh` or `stale`. Stale claims remain visible, while expired claims are omitted. Source `health` may be `healthy`, `degraded`, `unavailable`, or `null`; it may be `null` in the current inactive P3 production projection. Source `cache_state` is `absent`, `available`, or `corrupt`.

The endpoint only reads existing state. A `GET` performs no network request or refresh and does not initialize, publish, or repair a cache. Cache absence does not prevent the curated response. A corrupt or unreadable cache is bounded as `corrupt` and degrades to curated-only evidence.

An unknown or unmapped item returns a sanitized `404` without selecting or reading a dynamic source. An invalid request clock or unexpected internal projection failure returns a bounded, sanitized `500` response.

This projection introduces no mutation or execution authority.

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
