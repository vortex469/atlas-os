<div align="center">

# Atlas OS

### Own Your Infrastructure. Through Conversation.

**A conversational infrastructure platform for understanding, operating, and automating modern infrastructure.**

![Status](https://img.shields.io/badge/status-active%20development-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Release](https://img.shields.io/badge/release-Foundry%200.1-orange)

</div>

---

## Infrastructure should be understandable.

Modern infrastructure is spread across dozens of tools.

Docker.
Proxmox.
Kubernetes.
Home Assistant.
SSH.
Cloud providers.
Dashboards.

Atlas brings them together into a single platform that understands your infrastructure before it changes it.

Instead of asking:

> "What command do I run?"

Atlas helps answer:

> **"What is happening, what should I do next, and why?"**

---

# What is Atlas?

Atlas is an open-source conversational infrastructure platform.

It analyzes infrastructure, explains deployments, identifies risks, recommends actions, and eventually executes approved changes through a unified operational experience.

Atlas is designed for:

- Homelabs
- Self-hosted services
- Edge infrastructure
- Small business environments
- Enterprise platforms

---

# Philosophy

Atlas follows one simple rule.

> **Understanding comes before automation.**

Every deployment follows the same workflow.

```text
Understand

↓

Explain

↓

Recommend

↓

Approve

↓

Execute

↓

Observe
```

Automation without understanding creates surprises.

Atlas is designed to eliminate those surprises.

---

# Components

## Atlas Core

The backend reasoning engine.

Current capabilities:

- Deployment analysis
- Risk assessment
- Planning engine
- Provider abstraction
- Versioned REST API with typed contracts
- Standardized API errors and request tracing
- Provider action discovery and execution
- Persistent, sanitized provider action history
- Aggregated dashboard, health, and AI status
- Modular architecture

---

## Forge

Deployment analysis workspace.

Features:

- Deployment Briefs
- Docker Compose analysis
- Diagnostics
- Execution planning
- Rich component inspection
- Risk visualization
- Application recognition *(in progress)*

---

## Mission Control

Operational dashboard.

Provides:

- Infrastructure overview
- Live Atlas and service health
- Provider catalog and drill-down pages
- Service details and health refresh
- Confirmed, parameterized provider operations
- Filterable action history with request correlation
- ACE findings and recommendations

---

## Orion *(Planned)*

Conversational infrastructure assistant.

Future capabilities:

- Voice interaction
- Guided troubleshooting
- Operational recommendations
- Conversational infrastructure management

---

# Architecture

```text
 Docker Compose
 Kubernetes
 Terraform
 Infrastructure Providers
          │
          ▼
 Deployment Analysis
          │
          ▼
 Knowledge Engine
          │
          ▼
   Risk Assessment
          │
          ▼
  Planning Engine
          │
          ▼
 Mission Control
```

---

# Current Features

- Deployment analysis
- Deployment Briefs
- Docker Compose parser
- Risk engine
- Planning engine
- Diagnostics
- Modular analyzers
- Provider abstraction
- Atlas API v1
- Unified dashboard control plane
- Standardized API error contracts
- Proxmox, Docker, Home Assistant, and Ollama integration
- Ollama model lifecycle operations
- Live Mission Control service health
- Provider-backed operational actions
- Operations workspace and action audit visibility
- JSON and CSV audit export
- Confirmed retention maintenance
- Provider and UTC date-range audit filtering
- Filter-aware audit exports
- 168 Atlas Core tests
- Mission Control component tests, lint, and production build gates

---

# Roadmap

## Foundry (Current)

- Deployment analysis
- Forge
- Mission Control
- Risk engine
- Planning engine
- Atlas API v1
- Service health and provider operations
- Action history and audit visibility
- Audit export and retention administration

---

## Knowledge Engine

- Application recognition
- Knowledge catalog
- Infrastructure expertise
- Resource estimation
- Best-practice recommendations

---

## Deployment Platform

- Approval workflows
- Provider execution
- Rollback support
- Live deployment monitoring

---

## Conversational Infrastructure

- Orion Assistant
- Voice interaction
- Cross-provider reasoning
- Guided troubleshooting
- Conversational operations

---

# Why Atlas?

Most infrastructure software focuses on automation.

Atlas focuses on understanding.

Automation is simply the final step.

---

# Contributing

Atlas is under active development.

Contributions are welcome, including:

- Documentation
- Providers
- Knowledge catalog entries
- UI improvements
- Testing
- Infrastructure integrations

---

# License

MIT
