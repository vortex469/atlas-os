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
- OPNsense
- Frigate
- Obsidian
- Qdrant
- Inventory-backed services

Planned

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
- Expected Docker container state
- OPNsense firmware posture
- OPNsense firmware severity thresholds

Planned

- Obsidian provider policies

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

✔ Audit Detail Views and Shareable Deep Links

✔ Dashboard Refresh and Service Detail Coverage

✔ Dynamic Policy Reload

✔ Docker Expected State

✔ Atlas Doctor Integration

✔ OPNsense Provider

✔ Provider-Backed ACE Findings

✔ OPNsense Policy Thresholds

✔ Provider Intelligence Time Budgets

✔ Frigate Provider

✔ Frigate Camera Health Policies

✔ Provider Intelligence Timing Telemetry

✔ Obsidian Provider

✔ Qdrant Provider

✔ Obsidian Vault Policies

225 Atlas Core tests collected.

19 Mission Control component tests passing.

---

# Current Sprint

Provider Intelligence

Next work

- n8n provider

---

# Repository

GitHub

vortex469/atlas-os
