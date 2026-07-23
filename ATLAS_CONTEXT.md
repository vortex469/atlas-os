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

18 unit tests passing.

---

# Current Sprint

Sprint 3.4

Next work

- Dynamic policy reload
- Docker expected state
- Atlas Doctor integration
- OPNsense provider

---

# Repository

GitHub

vortex469/atlas-os
