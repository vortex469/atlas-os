# P3 Discovery Evidence: Completion Brief for Codex

> Planning brief. This document defines the remaining work to close Atlas V0.12
> P3 (the read-only discovery evidence projection). It does not change P3a/P3b
> behavior and it must not alter the committed P3b contract in `581ea50`.

## Objective

The evidence endpoint `GET /api/v1/discovery/items/{item_id}/evidence` is
implemented and tested as a bounded, read-only merged projection of curated
catalog data and dynamic release evidence. Three concrete gaps remain. Close all
three:

1. Wire a real source-health provider so `source_states[].health` stops being
   `null` in production.
2. Wire a curated release-claim provider so `conflict_state` can actually reach
   `agreement` / `curated_conflict` instead of only the dynamic-only states.
3. Document the evidence endpoint (and the proposals endpoints) in
   `docs/discovery-center/API.md`.

Each gap is independent. Land them as separate, reviewable changes.

## Current state (verified)

The production dependency is constructed in exactly one place:

- `services/atlas-core/app/services/discovery_dynamic_projection.py`
  `get_discovery_projection_service()` builds
  `DynamicDiscoveryProjectionService(catalog, cache_reader)` with **no**
  `health_provider` and **no** `curated_claim_provider`. Both constructor
  arguments are optional (`DynamicDiscoveryProjectionService.__init__`,
  `app/discovery/dynamic_projection.py:310`), so the service runs with both
  providers `None` today.

Because both providers are `None`, the projection degrades to a fixed
baseline:

- `source_states[].health` is always `null`.
  `DynamicDiscoveryProjectionService._read_health` (`dynamic_projection.py:417`)
  returns `None` when `self._health_provider is None`.
- `conflict_state` is computed by
  `evaluate_release_conflict(curated_claim=None, dynamic_claims=claims)`
  (`dynamic_projection.py:394`), so `curated_claim` is always `None`. The
  public conflict reducer `_public_conflict_state` (`dynamic_projection.py:522`)
  and the evaluation reducer `_conflict_state`
  (`app/discovery/dynamic_evaluation.py:323`) both treat a `None` curated claim
  as the dynamic-only branch, so production can only produce
  `none`, `agreement`, or `dynamic_conflict`. `curated_conflict` is unreachable
  until a curated claim provider is wired.

The merged projection model is `DiscoveryMergedItemProjection` with
`schema_version = MERGED_ITEM_SCHEMA` and fields `catalog_item_id`, `curated`,
`dynamic_claims[]`, `source_states[]`, `conflict_state`.

### Values the endpoint already produces (do not change)

- `source_states[].health`: `healthy | degraded | unavailable | null`
  (`DynamicSourceHealth`, `app/discovery/dynamic_sources.py:99`).
- `source_states[].cache_state`: `absent | available | corrupt`
  (`DynamicCacheState`, `app/discovery/dynamic_cache.py`).
- `dynamic_claims[].freshness`: `fresh | stale | expired`. `stale` claims are
  kept; `expired` claims are dropped (`_reevaluate_snapshot`,
  `dynamic_projection.py:462`; `evaluate_freshness`,
  `dynamic_evaluation.py:246`). Freshness windows: `FRESH_WINDOW = 24h`,
  `STALE_WINDOW = 30d` (`dynamic_evaluation.py:23`).
- `conflict_state`: `none | agreement | dynamic_conflict | curated_conflict`
  (`ConflictState`, `app/discovery/dynamic_evaluation.py`).
- Curated catalog data is always preserved and always wins over dynamic facts;
  a dynamic claim can never override a curated value.
- Unknown items return a sanitized 404 and never read the cache
  (`test_unknown_item_preserves_sanitized_404_and_does_not_read_cache`).
- A naive (timezone-less) request clock is rejected and fails closed with a
  sanitized 500 (`test_naive_request_clock_fails_closed_without_synthesizing_time`,
  `test_clock_failure_does_not_leak_raw_details`).
- Repeated GETs are byte-deterministic
  (`test_repeated_get_is_byte_deterministic`,
  `test_source_and_claim_permutations_are_deterministic`).

### Fixed production wiring (do not change)

- Item-to-source mapping is fixed to `frigate` only:
  `ITEM_SOURCE_MAPPING = {"frigate": (FRIGATE_ADAPTER_ID,)}`
  (`app/discovery/dynamic_projection.py`). Enforced by
  `test_production_mapping_and_cache_root_remain_fixed`.
- Cache root is fixed to
  `DISCOVERY_CACHE_ROOT = Path("/opt/atlas/data/cache/discovery")`
  (`services/discovery_dynamic_projection.py:15`).
- The single dynamic source adapter is
  `FRIGATE_ADAPTER_ID = "frigate-github-latest-release-v1"`
  (`app/discovery/dynamic_sources.py:26`), a `github_latest_release` source at
  trust tier `supplemental`, origin class `public_https_allowlisted`, against
  `api.github.com/repos/blakeblackshear/frigate/releases/latest`.

## Constraints (enforced by existing tests; keep passing)

The read-only contract of the evidence route is enforced by
`services/atlas-core/app/routes/test_discovery_evidence_isolation.py`:

- The route module must not import any authority or side-effect module. The
  forbidden token set includes `dynamic_sources`, `dynamic_refresh`,
  `provider_intents`, `policies`, `provider_actions`, `operational_dispatch`,
  `execution_candidates`, `planning`, `approvals`, `agents`, `backup`,
  `restore`, `recovery` (`test_evidence_route_has_no_authority_or_side_effect_dependencies`).
  **Consequence:** the evidence route and its dependency must never call the
  adapter or the refresh coordinator. A health provider wired into the route
  may only *read* already-computed in-memory health; it must not trigger a
  fetch or a network call.
- The route and dependency sources must not contain `.initialize(`,
  `.publish(`, `.refresh(`, `.fetch(`, `open(`, `os.open`, `.rename(`,
  `.unlink(`, `.chmod(`, `.chown(`, `flock`. The dependency must keep
  `datetime.now(UTC)` and `DiscoveryCacheStore(DISCOVERY_CACHE_ROOT)` and must
  not introduce `Query(` (`test_route_and_dependency_construction_are_read_only`).
- `frigate` is the only mapped item; unknown or unmapped items must never read
  the dynamic cache (`test_unmapped_curated_item_never_reads_dynamic_cache`,
  `test_path_shaped_unknown_items_cannot_select_cache_or_source`).

The P3b behavioral contract lives in
`services/atlas-core/app/routes/test_discovery_evidence.py` (read-only GET,
no network refresh/publish/initialize, bounded corrupt-cache handling,
byte-determinism, sanitized errors, exact GET-only OpenAPI). The projection and
cache unit contracts live in
`app/discovery/test_dynamic_projection.py` and
`app/discovery/test_dynamic_cache.py`. All of these must keep passing.

## The three gaps and the work for each

### Gap 1 — source health is always `null` in production

Root cause. `DynamicSourceHealth` values are produced by the dynamic-source
adapter path and are held **in memory only**. The P2a cache store
(`app/discovery/dynamic_cache.py`) persists release-fact generations, not
health. Nothing in production populates a `SourceHealthProvider`, so
`_read_health` always returns `None`.

What to build.

1. Define a `SourceHealthProvider`-conforming object whose
   `read_health(source_id) -> DynamicSourceHealth | None` reads the last
   observed health for a source from in-memory state written by the
   (separately-scheduled) refresh/adapter path. It must be pure read: no
   network, no filesystem, no cache mutation.
   - `read_health` must return `None` (not raise) for an unknown
     `source_id`, and must tolerate an absent observation.
   - The provider protocol is structural
     (`app/discovery/dynamic_projection.py:209`), so no inheritance is
     required; match the signature exactly.
2. Wire it into the production constructor:
   `get_discovery_projection_service()` in
   `services/discovery_dynamic_projection.py` should pass
   `health_provider=<the provider>` as a keyword argument. Do **not** pass it
   through the route; pass it at the service-construction site only.
3. Keep health independent of freshness: a source can be `healthy` with a
   stale cache or `unavailable` with a fresh cache. Do not derive health from
   cache state or freshness.

Guardrails.

- A health provider that raises must be swallowed by the existing boundary in
  `_read_health` and yield `null` — do not change that boundary to propagate
  errors.
- Do not add `dynamic_sources` or `dynamic_refresh` imports to
  `app/routes/discovery.py`. If the provider object needs to live in a module
  that imports those, it must be imported only in
  `services/discovery_dynamic_projection.py`, never in the route.
- Add/extend tests mirroring `test_missing_or_failed_health_observation_is_null`
  and `test_health_is_independent_from_freshness` at the service level, plus one
  production-wiring test asserting the wired provider returns a non-`null`
  health for `frigate` when an observation exists and `null` when it does not.

### Gap 2 — no curated release claim is wired, so `curated_conflict` is unreachable

Root cause. There is **no** first-class curated release-claim field in the
catalog. `DiscoveryItem` does have a `version: str | None` field
(`app/discovery/models.py:200`), but `catalog/applications/frigate.yaml` leaves
it unset (it is `None` in production) and, by contract, it must not be reused
as a release claim. The evaluation layer already supports a curated claim
(`ExplicitCuratedReleaseClaim`, `app/discovery/dynamic_evaluation.py:126`,
`schema_version = "discovery-curated-release-claim-v1"`), but
`get_discovery_projection_service()` passes no
`curated_claim_provider`, so `curated_claim` is always `None` and the reducer
can only reach the dynamic-only states.

What to build.

1. Decide the curated claim's source of truth and make it explicit.
   - Preferred: add an explicit, versioned release claim to the curated Frigate
     catalog data (a new field carrying `version` + `published_at`), and read it
     through the catalog. This is the honest representation: curated data
     already asserts a current release.
   - Do **not** reinterpret the existing `DiscoveryItem.version` field
     (`models.py:200`, currently `None` in `frigate.yaml`) as a curated release
     claim. That is explicitly rejected by
     `test_discovery_item_version_is_not_reinterpreted_as_curated_release`:
     the item's `version` and a dynamic claim's `version` are independent, and
     neither overrides the curated catalog value. The release claim must be a
     distinct, first-class curated value with its own `published_at`, not a cast
     of an unrelated catalog field.
2. Implement an `ExplicitCuratedClaimProvider`-conforming object whose
   `get_claim(item_id) -> ExplicitCuratedReleaseClaim | None` returns a
   validated `ExplicitCuratedReleaseClaim` for `frigate` (or `None` when no
   curated claim exists). The claim's `key` must be the canonical
   `latest_stable_release` fact key for `frigate`, and its `value` must match
   the `version`/`published_at` the curated data asserts.
   - `get_claim` must return `None` (not raise) when the claim is absent, and
     must validate identity: `_read_curated_claim`
     (`dynamic_projection.py:428`) already discards a claim whose
     `key.catalog_item_id` does not match the requested item.
3. Wire it into the production constructor as
   `curated_claim_provider=<the provider>` in
   `services/discovery_dynamic_projection.py`.

Guardrails.

- A curated claim never overrides the curated catalog value in the response; it
  only feeds `conflict_state`. Confirm the merged projection still surfaces the
  original `curated` entry unchanged.
- Keep the claim boundary fail-soft: a provider that raises yields `None` via
  the existing `_read_curated_claim` boundary. Do not change that boundary.
- Add/extend tests mirroring
  `test_explicit_typed_curated_agreement_and_conflict` and
  `test_supplemental_and_dynamic_conflict_states`, plus a production-wiring test
  asserting `frigate` reaches `agreement` when the curated claim equals the
  dynamic claim and `curated_conflict` when they differ.

### Gap 3 — `docs/discovery-center/API.md` does not document the evidence endpoint

Root cause. `docs/discovery-center/API.md` documents the discovery catalog
surface but does not document the P3b evidence endpoint, and it does not
document the proposals endpoints. The implementation and its tests are the
source of truth; the docs lag.

What to write. In `docs/discovery-center/API.md`, add a section for

- `GET /api/v1/discovery/items/{item_id}/evidence` (GET-only), documenting:
  - The request: no body, no query parameters (the dependency must not add
    `Query(`), no CSRF/write permission for anonymous GET.
  - The response envelope: `schema_version`, `catalog_item_id`, `curated`,
    `dynamic_claims[]` (each with `fact_kind`, `version`, `published_at`,
    `freshness`, and bounded `provenance`), `source_states[]` (each with
      `source_id`, `health`, `cache_state`), and `conflict_state`.
  - The exact value domains listed under "Values the endpoint already
    produces" above, including that `health` may be `null` and that `stale`
    claims are retained while `expired` claims are dropped.
  - The read-only guarantees: no network refresh, no cache
    initialize/publish, no side effects, byte-deterministic repeated GETs.
  - Error behavior: sanitized 404 for unknown items (cache is never read),
    sanitized 500 for a naive clock (time is never synthesized), bounded
    corrupt-cache handling that returns the curated-only projection.
  - The curation precedence: curated catalog data always wins over dynamic
    facts.
- The proposals endpoints, documented to the same fidelity as the rest of the
  file.

Guardrails.

- Do not document behavior that does not exist. Where a value is currently
  `null` in production (see Gap 1), document the value as "may be null until a
  health provider is wired" only if Gap 1 is not landed in the same change;
  otherwise document the populated values.
- Keep the docs consistent with the fixed wiring: `frigate` is the only
  mapped dynamic item, and the source is the Frigate GitHub latest-release
  adapter.
- `test_legacy_item_json_and_openapi_do_not_gain_evidence_fields` pins that the
  legacy item JSON and OpenAPI do **not** gain evidence fields. The new docs
  must describe the evidence endpoint as a distinct route, not as new fields on
  the legacy item response.

## Suggested commit boundaries

- Change A: source-health provider + production wiring + tests (Gap 1).
- Change B: curated release-claim provider + curated-data field + production
  wiring + tests (Gap 2).
- Change C: `docs/discovery-center/API.md` evidence + proposals documentation
  (Gap 3).

Each change must leave the full existing test suite green, including
`test_discovery_evidence.py`, `test_discovery_evidence_isolation.py`,
`test_dynamic_projection.py`, and `test_dynamic_cache.py`.

## Definition of done

- `source_states[].health` is populated from a real (in-memory, read-only)
  provider for `frigate` and remains `null` when no observation exists.
- `conflict_state` can reach `agreement` and `curated_conflict` for `frigate`
  via a wired, validated curated release claim, without ever overriding the
  curated catalog value.
- `docs/discovery-center/API.md` documents the evidence endpoint (GET-only,
  envelope, value domains, read-only guarantees, error behavior, curation
  precedence) and the proposals endpoints.
- No import of `dynamic_sources` or `dynamic_refresh` (or any forbidden
  authority/side-effect module) appears in the evidence route, and the route
  and its dependency contain no forbidden side-effect tokens.
- The fixed wiring (`frigate`-only mapping, `DISCOVERY_CACHE_ROOT`) is
  unchanged, and all existing P3a/P3b tests pass unmodified.
