# Atlas OS

## Vision

Atlas OS is a local-first infrastructure operating system designed to monitor,
reason about, and automate a homelab environment.

Assistant: Orion

Reasoning Engine: ACE (Atlas Cognitive Engine)

Release: Foundry

---

# Architecture

Atlas Core
    ↓
Providers
    ↓
Findings
    ↓
Assessment Engine
    ↓
Situation Report
    ↓
REST API

---

# Current Providers

Implemented

- Proxmox
- Docker
- Home Assistant
- Ollama
- Inventory-backed services

Planned

- OPNsense
- Frigate
- Obsidian
- Qdrant
- n8n

---

# Configuration

config/

    atlas.yaml

    policies.yaml

inventory/

    services.yaml

---

# Policy System

ACE supports operational policy.

Current

- Expected Proxmox guest state
- Ignored Home Assistant entities

Planned

- Docker expected container state
- OPNsense policies
- Frigate policies

---

# Development Standards

- Production-quality code
- Type hints everywhere
- Pydantic models
- Unit tests for every feature
- Small incremental commits
- Architecture first
- Reusable components
- No duplicated logic

---

# Current Milestones

✔ Situation Report

✔ Structured Findings

✔ Assessments

✔ Recommendations

✔ Policy Engine

✔ Proxmox Expected State

✔ Home Assistant Expected State

✔ Atlas API v1

✔ Unified Dashboard API

✔ Provider Action Engine

✔ Mission Control Service Health

✔ Confirmed and Parameterized Operations

✔ Action History and Audit Visibility

✔ Persistent Audit Storage and Retention

✔ Audit Export and Retention Administration

✔ Provider and Date-Range Audit Filtering

✔ Audit Pagination and Action/Request Search

169 Atlas Core tests passing.

10 Mission Control component tests passing.

---

# Current Sprint

Foundry Dashboard and Operations

Next work

- Audit detail view and shareable deep links
- Frontend coverage for dashboard refresh and service details
- Dynamic policy reload
- Docker expected state
- Atlas Doctor integration
- OPNsense provider

---

# Repository

GitHub

vortex469/atlas-os
