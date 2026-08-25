# Atlas OS Current Context

## Released baseline

Atlas v0.15.0 is released as `atlas-v0.15.0` at
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab` (2026-08-25).

## Production topology

The base production Compose deployment contains Core, Agent, three one-shot
authentication stagers, the execution worker and relay, the egress proxy, and
Mission Control. Optional overlays provide HTTPS ingress through Atlas Edge,
Core-owned operator authentication, and explicit Provider Intent activation.

## Authority boundaries

- Legacy provider actions are a separate provider-specific mutation surface.
- Provider Intent can mutate only Proxmox QEMU `monitoring-policy` and requires
  explicit activation and `provider_intent:update` operator authority.
- Hardened operational dispatch is exactly
  `restart-service / proxmox / qemu`.
- Repository candidate execution is exactly `update-compose-stack`.
- Discovery is GET-only/read-only. Its proposals, compatibility results,
  release intelligence, image observations, grounding, and provenance confer
  no execution authority.
- Backup and restore are operator maintenance tools, not Agent intents.

There is no automatic remediation, approval, update, deployment, rollback, or
release publication.

## Provider Intent

The released schema-v2 identity-bound store can be activated with
`compose.provider-intent-activated.yaml`. When activated and available it is
authoritative for Proxmox QEMU monitoring expectations; retained YAML guest
values are legacy import evidence, not competing authority. Provider Intent is
not a general provider-action or operational execution framework.

## Discovery through v0.14

Discovery includes curated D0-D9 capabilities, v0.12 dynamic evidence/cache
and provenance, v0.13 compatibility and upgrade intelligence, and v0.14 exact
Compose image observation, accepted image-release evidence, informational
grounding, and provenance. Dynamic refresh is bounded and opt-in. The generic
image collector remains inactive, with empty production registries and no
startup or scheduled wiring.

## Backup and restore

The v3 operator tooling covers the declared durable Atlas Core boundary and
Provider Intent state under its documented activation and compatibility
checks. Agent state and rebuildable Discovery cache are excluded. Restore
remains an explicit operator maintenance operation; it never becomes an Agent
execution request.

## Mission Control

Major released surfaces include overview/provider health, policies and
findings, provider management and Provider Intent, Discovery browsing/search/
compatibility/evidence, advisory proposals, operational review/history/
recovery, and Atlas Agent workflow views. Browser mutations require their
specific Core-owned authority and deployment gates.

## v0.15 released state

Atlas v0.15 has the theme **Deployment Image Grounding Operator Surface**: a
bounded, read-only, informational operator-facing surface over the released
v0.14 image grounding and provenance, with initial evidence breadth limited to
the accepted Home Assistant `2026.8.3` registry-attested proof. It adds no
collector, no scheduled collection, and no execution, approval,
provider-intent, or remediation authority, and no Discovery-to-dispatch
coupling.

P0 through P5 and production acceptance are complete. The release is
`atlas-v0.15.0` at `850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`. P1 composes the existing
`DeploymentBinding`, repository Compose observation, accepted evidence, and
`ground_deployment_image` semantics into a deterministic fail-closed local
read-only model. P2 exposes the bounded, redacted GET-only projection at
`GET /api/v1/discovery/items/{item_id}/image-grounding`. P3 renders status,
release, deployment binding, observed image, accepted evidence, source class,
source identity, and attestation time in Mission Control as advisory
information, with no action controls. P4 proves
there is no startup, scheduled, or request-time acquisition and that a GET
uses only already-accepted local evidence and reviewed local readers, without
triggering GHCR access, registry acquisition, Sigstore verification, collector
execution, or evidence refresh. It also proves isolation, redaction, and
unchanged authority contracts.
P5 completed exact-SHA release validation and read-only production acceptance.
No phase may add evidence or bindings, acquire or verify evidence at runtime,
persist projection state, silently choose a source, or create a mutation or
execution path.

## Deferred capabilities

Semantic Discovery (D11), private/community catalogs (D12), additional
operational and repository intents, broader Provider Intent domains, generic
image collection, and distributed orchestration remain uncommitted.
