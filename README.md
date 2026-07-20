<div align="center">

# Atlas OS

### Own Your Infrastructure. Through Conversation.

**An open-source conversational infrastructure operating system.**

*Atlas helps you understand your infrastructure before it helps you change it.*

---

**Current Release:** Foundry 0.1

</div>

---

# What is Atlas?

Atlas is an intelligent infrastructure platform designed to help you understand, manage, and eventually automate your entire infrastructure from a single interface.

Instead of switching between Docker, Proxmox, Home Assistant, Kubernetes, SSH sessions, and dozens of dashboards, Atlas provides one place to analyze deployments, assess risk, plan execution, and guide operations.

Atlas is built around a simple idea:

> **Understanding comes before automation.**

---

# Why Atlas?

Most infrastructure tools help you automate.

Atlas helps you understand.

Before Atlas executes a deployment, it explains:

- What it discovered
- What risks exist
- What it plans to do
- Why it recommends that action

Every recommendation is backed by reasoning.

---

# Core Principles

Atlas is built around four guiding principles.

- 🧠 Understand before acting
- 🔍 Explain every recommendation
- ✅ Require approval before execution
- 🤖 Automate only after understanding

These principles influence every feature in Atlas.

---

# Components

## Atlas Core

The reasoning engine behind Atlas.

Current capabilities include:

- Deployment analysis
- Risk assessment
- Planning engine
- Provider abstraction
- REST API
- Modular analyzer architecture

---

## Forge

Deployment analysis workspace.

Current features include:

- Deployment Briefs
- Docker Compose analysis
- Diagnostics
- Risk analysis
- Rich component inspection
- Execution planning
- Application recognition *(in progress)*

---

## Mission Control

Operational dashboard for Atlas.

Mission Control provides:

- Deployment review
- Infrastructure overview
- Operational dashboards
- Approval workflows
- Future execution management

---

## Orion *(Planned)*

Conversational infrastructure assistant.

Future capabilities:

- Voice interaction
- Infrastructure explanations
- Guided troubleshooting
- Operational recommendations
- Intelligent deployment assistance

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
            Risk Engine
                 │
                 ▼
         Planning Engine
                 │
                 ▼
          Mission Control
```

---

# Example Workflow

```text
Paste Deployment

        │

        ▼

Atlas analyzes deployment

        │

        ▼

Deployment Brief

        │

        ▼

Review Risks

        │

        ▼

Approval

        │

        ▼

Execution
```

---

# Roadmap

## Foundry (Current)

- Deployment analysis
- Deployment Briefs
- Risk engine
- Planning engine
- Forge UI
- Mission Control

---

## Knowledge Engine

- Application recognition
- Knowledge catalog
- Best-practice recommendations
- Infrastructure expertise
- Resource estimation

---

## Deployment Platform

- Approval workflow
- Provider execution
- Rollback support
- Live deployment monitoring

---

## Conversational Infrastructure

- Orion Assistant
- Voice interaction
- Conversational operations
- Guided troubleshooting
- Cross-provider reasoning

---

# Project Status

Atlas is under active development.

The architecture is stabilizing while new capabilities are being added.

Breaking changes may occur before the first stable release.

---

# Contributing

Contributions are welcome.

Whether you're improving documentation, adding provider support, expanding the knowledge catalog, or helping build new features, we'd love your help.

---

# License

MIT
