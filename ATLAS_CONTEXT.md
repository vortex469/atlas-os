# Atlas OS Current Context

## Released baseline

Atlas v0.14.0 is released as `atlas-v0.14.0` at
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7` (2026-08-24).

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

## Deferred capabilities

Semantic Discovery (D11), private/community catalogs (D12), additional
operational and repository intents, broader Provider Intent domains, generic
image collection, and distributed orchestration remain uncommitted. No v0.15
scope is selected here.
