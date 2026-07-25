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
- n8n
- Inventory-backed services

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
- Frigate camera health thresholds
- Obsidian vault health
- Qdrant collection expectations
- n8n workflow expectations
- Provider intelligence performance thresholds

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

✔ n8n Provider

✔ Qdrant Collection Policies

✔ n8n Workflow Policies

✔ Mission Control Provider Intelligence Telemetry

✔ Provider Policy API and Mission Control Visibility

✔ Provider Policy Detail Views

✔ Policy Reload Health Telemetry

✔ Persistent Provider Intelligence Trend History

✔ Structured Policy Validation Diagnostics

✔ Provider Telemetry History Filtering

✔ Policy Diagnostics Operator Examples

✔ Provider Telemetry History Export

✔ Provider Telemetry Retention Administration

✔ Provider Telemetry Retention Detail View

✔ Provider-Specific Telemetry Trends

✔ Provider Intelligence Performance Policies

✔ Provider Performance Threshold Overlays

✔ Atlas Core Full-Suite Hang Remediation

✔ Foundry Dependency and Packaging Audit

✔ Foundry Release Documentation Audit

✔ Foundry Release Identifier Consistency

✔ Foundry Production Deployment Packaging

✔ Foundry Container Release Gates

✔ Foundry Release Candidate Audit

260 Atlas Core tests collected.

36 Mission Control component tests passing.

---

# Current Sprint

Foundry Release Hardening

Next work

- Operator credential rotation and release approval

---

# Repository

GitHub

vortex469/atlas-os
