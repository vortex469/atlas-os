# Atlas OS

> Own Your Infrastructure. Through Conversation.

Atlas is an open-source conversational infrastructure operating system.

Instead of managing servers, containers, virtual machines, and home automation through dozens of separate interfaces, Atlas provides a single intelligent platform that understands your infrastructure, explains it, and helps you operate it safely.

Atlas is designed for homelabs today and enterprise infrastructure tomorrow.

---

## Vision

Infrastructure should be understandable.

Before Atlas executes a deployment, it explains:

- What it found
- What it plans to do
- What risks exist
- Why it recommends a particular action

Atlas helps you understand your infrastructure before it helps you change it.

---

## Current Features

### Forge

Analyze Docker Compose deployments.

- Deployment Briefs
- Risk Analysis
- Deployment Planning
- Diagnostics
- Application Recognition (in progress)

### Atlas Core

- Deployment analysis pipeline
- Risk engine
- Planning engine
- Modular analyzer architecture
- Provider abstraction
- REST API

### Mission Control

Modern web interface for Atlas.

- Deployment analysis
- Operational dashboards
- Review workflows
- Execution planning

---

## Roadmap

### v0.8 — Knowledge Engine

- Application recognition
- Knowledge catalog
- Deployment recommendations
- Resource estimation

### v0.9 — Infrastructure Expertise

- Best-practice recommendations
- Documentation integration
- Cross-service reasoning

### v1.0 — Deployment Platform

- Approval workflow
- Provider execution
- Rollback support
- Live monitoring

---

## Philosophy

Atlas is built around four principles.

1. Understand first.
2. Explain every recommendation.
3. Require approval before execution.
4. Automate only after understanding.

---

## Architecture

Compose / Kubernetes / Providers

↓

Deployment Analysis

↓

Knowledge Engine

↓

Risk Engine

↓

Planning Engine

↓

Mission Control

---

## Status

Atlas is currently under active development.

Current release:

Foundry 0.1

The project is evolving rapidly and breaking changes may occur while core architecture is being established.

---

## License

MIT
