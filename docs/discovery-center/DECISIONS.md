# Atlas Discovery Center Decisions

This document records D0 architecture decisions for Discovery Center. D0 is documentation only and does not implement runtime behavior.

## DC-D0-001: Discovery Center is provider-neutral

Status: Accepted

Context: Atlas supports providers such as Proxmox, Docker, Home Assistant, OPNsense, Frigate, Ollama, Qdrant, n8n, Obsidian, and inventory-backed services. Discovery Center must support catalog knowledge across providers and domains.

Decision: Discovery Center models catalog items, capabilities, requirements, relationships, compatibility, and provenance without hard-coding one provider.

Consequences: Provider data may be projected into Discovery Center compatibility checks, but Discovery Center should not import provider clients directly.

## DC-D0-002: YAML catalog is the initial authority

Status: Accepted

Context: Atlas already has YAML application definitions in the Knowledge Engine. Atlas also values local-first operation and deterministic behavior.

Decision: The curated YAML catalog is the initial authoritative source for Discovery Center facts.

Consequences: Dynamic ingestion may supplement curated data later, but must not silently override curated facts. YAML entries must validate before use.

## DC-D0-003: Discovery Center is read-only by default

Status: Accepted

Context: Discovery Center answers knowledge and compatibility questions. Atlas has separate approval boundaries for policy changes and execution.

Decision: Discovery Center must be read-only by default.

Consequences: It must not install packages, start containers, modify configuration, open ports, write secrets, or apply recommendations.

## DC-D0-004: Orion owns recommendations

Status: Accepted

Context: Compatibility evidence can inform user action, but deciding what the user should do is product recommendation behavior.

Decision: Orion owns recommendations, priority, urgency, and user-facing reasoning about whether to install, change, investigate, or defer something.

Consequences: Discovery Center exposes facts and compatibility evidence. Orion may consume that evidence but remains the owner of recommendations.

## DC-D0-005: Atlas Agent owns execution

Status: Accepted

Context: Discovery Center must not execute changes. Atlas Agent is the intended future boundary for approved change execution.

Decision: All future executable work must be handed to Atlas Agent and pass through approval-controlled planning, execution, verification, review, and commit workflow.

Consequences: Discovery Center may produce structured handoff context in a future milestone, but it must not execute or bypass approval.

## DC-D0-006: Knowledge Engine relationship remains neutral in D0

Status: Accepted

Context: The existing Knowledge Engine includes YAML application catalog, matching, assessment, and rule behavior. Discovery Center has broader scope.

Decision: D0 describes Knowledge Engine as the current predecessor and a source of reusable concepts. It does not decide that Knowledge Engine becomes only a consumer.

Consequences: D1-D3 must determine whether Discovery Center extends, migrates, absorbs, or replaces individual Knowledge Engine components.

## DC-D0-007: Dependencies are primarily relationships

Status: Accepted

Context: Discovery Center needs to describe dependencies without making every dependency a top-level catalog item.

Decision: Dependencies are primarily modeled as relationships such as depends-on, requires, provides, consumes, integrates-with, and conflicts-with.

Consequences: A dependency may still be represented as an item when independently discoverable, such as PostgreSQL, MQTT, Redis, or an Ollama model.

## DC-D0-008: Compatibility findings are evidence-based

Status: Accepted

Context: Compatibility can influence user trust and future actions.

Decision: Compatibility statuses must be deterministic and backed by explicit evidence before semantic or AI-based behavior is used.

Consequences: AI may summarize or assist later, but deterministic evidence remains the source of truth for compatibility results.

## DC-D0-009: Offline-first behavior is required

Status: Accepted

Context: Atlas is local-first and must remain useful without internet access.

Decision: Discovery Center must operate from local curated catalog data first.

Consequences: Dynamic source adapters are optional future supplements. Missing online data should produce unknown or needs-review compatibility where appropriate, not break local catalog use.

## DC-D0-010: Community and private catalogs are future work

Status: Accepted

Context: Operators may eventually want private catalogs, and the community may contribute shared catalog entries.

Decision: D0 records the need for community and private catalogs but defers implementation to D12.

Consequences: Future catalogs must include validation, trust, provenance, conflict handling, and runtime-state storage rules.
