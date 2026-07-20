<div align="center">

# Atlas OS

### Own Your Infrastructure. Through Conversation.

**An open-source conversational infrastructure operating system.**

Atlas helps you understand your infrastructure before it helps you change it.

---

**Current Release**

**Foundry 0.1**

</div>

---

# What is Atlas?

Atlas is an intelligent infrastructure platform designed to analyze, understand, and eventually operate modern infrastructure through conversation.

Instead of managing Docker, Proxmox, Home Assistant, Kubernetes, SSH sessions, and dozens of dashboards separately, Atlas provides a unified platform that explains your infrastructure, recommends actions, and safely guides execution.

Atlas is built around one simple philosophy:

> **Understanding comes before automation.**

---

# Why Atlas?

Most infrastructure tools help you automate.

Atlas helps you understand.

Before Atlas executes a deployment it answers four questions:

- **What did I find?**
- **What risks exist?**
- **What do I recommend?**
- **Why?**

Every recommendation is backed by analysis rather than automation alone.

---

# Core Principles

Atlas is built around four guiding principles.

- 🧠 Understand before acting
- 🔍 Explain every recommendation
- ✅ Require approval before execution
- 🤖 Automate only after understanding

These principles influence every subsystem inside Atlas.

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
- Deployment planning
- Risk analysis
- Diagnostics
- Rich component inspection
- Application recognition *(in progress)*

---

## Mission Control

Modern operations interface.

Mission Control provides:

- Deployment review
- Infrastructure overview
- Operational dashboards
- Future execution management

---

## Orion *(Planned)*

Conversational infrastructure assistant.

Future capabilities include:

- Voice interaction
- Infrastructure explanations
- Guided troubleshooting
- Infrastructure recommendations
- Conversational operations

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

Review Findings

        │

        ▼

Approve

        │

        ▼

Execute
```

---

# Current Status

Atlas currently supports:

- Docker Compose deployment analysis
- Deployment Brief generation
- Risk analysis
- Execution planning
- Diagnostics
- Provider abstraction
- Mission Control web interface

Currently under development:

- Application recognition
- Knowledge catalog
- Infrastructure expertise
- Approval workflows
- Provider execution

---

# Roadmap

## Foundry (Current)

- ✅ Deployment analysis
- ✅ Deployment Briefs
- ✅ Risk engine
- ✅ Planning engine
- ✅ Forge UI
- ✅ Mission Control

---

## Knowledge Engine

- Application recognition
- Knowledge catalog
- Best-practice recommendations
- Resource estimation
- Infrastructure expertise

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
- Guided troubleshooting
- Cross-provider reasoning
- Conversational operations

---

# Project Status

Atlas is under active development.

Core architecture is stabilizing while new capabilities are being added.

Breaking changes should be expected before the first stable release.

---

# Contributing

Contributions are welcome.

Whether you're improving documentation, expanding the Knowledge Engine, adding providers, improving Mission Control, or building new capabilities, we'd love your help.

---

# License

MIT
