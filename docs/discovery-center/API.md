# Discovery Center API — Atlas v0.14

## Public contract

The v0.14 Discovery router is mounted under `/api/v1/discovery` and is
GET-only/read-only. It creates no candidate, intent, provider action, approval,
dispatch, update, deployment, or rollback.

Public GET endpoints are:

- `/api/v1/discovery`
- `/api/v1/discovery/items`
- `/api/v1/discovery/items/{item_id}`
- `/api/v1/discovery/items/{item_id}/evidence`
- `/api/v1/discovery/items/{item_id}/relationships`
- `/api/v1/discovery/items/{item_id}/compatibility`
- `/api/v1/discovery/search`
- `/api/v1/discovery/proposals`
- `/api/v1/discovery/proposals/{proposal_id}`

List and search endpoints provide bounded pagination and typed filters. Missing
items return 404, invalid queries 422, and unavailable catalog or compatibility
context 503. Response models in released code are authoritative for exact
fields and schemas.

## Dynamic evidence API

`GET /items/{item_id}/evidence` returns the merged projection. Curated catalog
claims remain authoritative; dynamic/cache facts are supplemental and carry
source, freshness, conflict, and health evidence. V0.13 release evaluation and
observed-version compatibility are read-only additions. V0.14 image grounding
and provenance, when present, are informational and convey no action authority.

## Internal v0.14 boundaries (not new public endpoints)

### DeploymentBinding

A code-reviewed binding maps one curated item to one exact repository Compose
file and service. It is an internal trust contract, not arbitrary filesystem
selection and not a public mutation API.

### Compose observation

The repository observer reads the exact bound service image and fails closed on
path, YAML, service, interpolation, or image ambiguity. It performs no pull,
update, restart, or deployment.

### Grounding

Grounding deterministically composes an accepted deployment observation with
accepted image-release evidence. It is derived read-only information.

### Provenance

Provenance preserves evidence identities and trust classes. In particular,
`REGISTRY_ATTESTED` evidence is not silently promoted to `CURATED`.

### Inactive image collector

The generic collector and transport exist as bounded internal code, but the
production descriptor and adapter registries are empty. No route, startup job,
scheduler, or user control activates collection. Reviewed immutable evidence
can be loaded without making collection a production capability.

## Release status

Dynamic evidence/cache shipped in v0.12, compatibility/upgrade intelligence in
v0.13, and trusted Compose image observation/grounding in v0.14. Atlas v0.14.0
is released; none of these features is pending or a release candidate.
