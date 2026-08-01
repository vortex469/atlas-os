# Atlas Discovery Center Context

Discovery Center is the planned provider-neutral catalog and compatibility subsystem for Atlas. It exists so Atlas can reason from structured local knowledge before offering recommendations or approved execution paths.

D0 is documentation only. It records the intended product and architecture context without claiming runtime Discovery Center functionality exists.

## Why Discovery Center exists

Atlas already observes infrastructure through providers, deployment analysis, policies, and health checks. It also has a current Knowledge Engine with YAML application definitions and deployment-plan assessment.

Discovery Center gives Atlas a broader structured catalog for answering:

- What applications, services, images, models, integrations, devices, and deployment methods does Atlas know about?
- What capabilities do they provide?
- What requirements and relationships do they have?
- Are they compatible with the current Atlas environment?

This enables Mission Control, Orion, and Atlas Agent to share a common factual base while preserving clear ownership boundaries.

## Current Atlas sources of truth

Current relevant sources include:

- `services/atlas-core/app/knowledge_engine/applications/*.yaml` for application knowledge.
- `services/atlas-core/app/knowledge_engine` loader, matcher, assessors, and rules.
- `services/atlas-core/app/catalog` application, capability, and requirement concepts.
- `services/atlas-core/app/deploy` deployment components, ports, storage, resources, risks, and planning models.
- `inventory/services.yaml` for known services and provider loading.
- Provider resources exposed through generic provider resource contracts.
- Atlas Runtime Foundation for mutable runtime state under `data/`.
- Provider connection and policy stores for user-owned runtime configuration.

Discovery Center should reuse these concepts where appropriate instead of duplicating them.

## Knowledge Engine relationship

The Knowledge Engine is the current predecessor for structured application knowledge and assessment behavior.

D0 keeps the relationship neutral. D1-D3 should evaluate individual Knowledge Engine components and decide whether Discovery Center should extend, migrate, absorb, or replace each one. The decision may differ by component. For example, YAML loading patterns may be reused directly, while application-only models may need broader Discovery Center item contracts.

## Product boundaries

Discovery Center answers what exists, what it provides, what it requires, and whether it appears compatible.

Orion owns recommendations. Orion decides whether the user should install, change, investigate, or defer something, and explains why it matters.

Atlas Agent owns execution. Future executable work must be handed to Atlas Agent and pass through approval-controlled planning, execution, verification, review, and commit workflow.

Mission Control owns the UI. It should present Discovery Center facts, compatibility evidence, and provenance without bypassing approval boundaries.

## Initial item types

Initial item types are:

- application
- service
- container image
- AI model
- integration
- hardware device
- deployment method

Dependencies are primarily relationships. A dependency may be represented as an item when independently discoverable, such as PostgreSQL, MQTT, Redis, or an Ollama model.

## Relationship terminology

Relationship terms include:

- dependency
- depends-on
- provides
- consumes
- requires
- integrates-with
- conflicts-with
- compatible-with
- incompatible-with
- runs-on
- deployed-by

Relationships should be structured, directional where applicable, and explainable.

## Expected data lifecycle

Initial lifecycle:

1. Curated YAML catalog is loaded from shipped source files.
2. YAML entries validate against typed models.
3. A repository exposes deterministic lookup and search.
4. A read-only API projects catalog entries and compatibility evidence.
5. Mission Control displays catalog facts and relationships.
6. Compatibility checks compare catalog requirements with observed Atlas environment data.
7. Orion consumes Discovery Center evidence when forming recommendations.
8. Future execution requests are handed to Atlas Agent only after user approval.

## Offline-first assumptions

Discovery Center should remain useful without internet access.

Rules:

- Curated local YAML loads without network access.
- Deterministic search does not require AI or online services.
- Compatibility can return `unknown` when required evidence is absent.
- Dynamic ingestion is optional and must not become a startup dependency.
- Cached or ingested facts must include provenance.

## Runtime-state assumptions

Shipped curated catalog files are immutable defaults. Future private catalogs, dynamic-source caches, indexes, or learned knowledge should live under runtime state, likely `data/knowledge/`, following Atlas Runtime Foundation rules.

Normal user changes through Mission Control must not dirty the Git checkout.

## User workflows

Initial user-facing workflows should be read-only:

- Browse known catalog items.
- Search for an application, service, model, integration, device, or deployment method.
- Inspect what an item provides and requires.
- Inspect dependencies and conflicts.
- Check compatibility against the current Atlas environment.
- See evidence and provenance for every result.

Future workflows may include Orion recommendations and Atlas Agent handoff, but Discovery Center itself remains non-executing.

## Glossary

- Item: a catalog entry such as an application, service, container image, AI model, integration, hardware device, or deployment method.
- Capability: something an item provides.
- Requirement: something an item needs.
- Relationship: a structured link between items, capabilities, requirements, providers, or environment facts.
- Compatibility: an evidence-backed status comparing requirements with an environment.
- Provenance: metadata describing where a catalog fact came from and how much it should be trusted.
