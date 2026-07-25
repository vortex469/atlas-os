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
- Live, validated operational policy reload
- Policy-aware Docker expected-state monitoring
- Atlas Doctor diagnostics through CLI and Operations API
- Read-only OPNsense health and diagnostics provider
- Concurrent provider-backed ACE findings
- Bounded provider intelligence collection
- Read-only Frigate camera health and version telemetry
- Aggregated dashboard, health, and AI status
- Modular architecture

---

### OPNsense provider

Add an `opnsense` service to `inventory/services.yaml`:

```yaml
services:
  opnsense:
    name: OPNsense
    host: firewall.home.arpa
    port: 443
    protocol: https
    health_endpoint: /api/core/firmware/status
    expected_status: [200]
    critical: true
    verify_tls: true
    # ca_bundle: /opt/atlas/config/certificates/opnsense.pem
```

Provide the read-only API credentials through the environment:

```dotenv
OPNSENSE_API_KEY=replace-me
OPNSENSE_API_SECRET=replace-me
```

TLS verification is enabled by default. Use `ca_bundle` for a private
certificate authority; disabling verification should be limited to
temporary development environments.

Firmware posture is controlled live through `config/policies.yaml`:

```yaml
opnsense:
  pending_update_warning_threshold: 1
  reboot_required_severity: warning
```

Set the update threshold to `null` to keep pending packages
informational. Reboot severity accepts `info`, `warning`, or
`critical`.

Provider finding collection uses a configurable deadline in
`config/atlas.yaml`:

```yaml
intelligence:
  provider_timeout_seconds: 10
```

The timeout must be greater than zero and no more than 60 seconds.
ACE situation reports include collection telemetry for operational
visibility:

```json
{
  "telemetry": {
    "provider_collection_duration_ms": 42.5,
    "provider_timeout_seconds": 10,
    "providers": [
      {
        "provider_id": "frigate",
        "provider_name": "Frigate",
        "status": "completed",
        "duration_ms": 38.2,
        "finding_count": 1
      }
    ]
  }
}
```

Provider status is `completed`, `timed_out`, or `failed`. Durations use
monotonic elapsed time and provider collection remains concurrent.

---

### Frigate provider

For the authenticated Frigate API, add this service to
`inventory/services.yaml`:

```yaml
services:
  frigate:
    name: Frigate
    host: frigate.home.arpa
    port: 8971
    protocol: https
    health_endpoint: /api/stats
    expected_status: [200]
    critical: false
    verify_tls: true
    # ca_bundle: /opt/atlas/config/certificates/frigate.pem
```

Provide a Frigate JWT through the environment when authentication is
enabled:

```dotenv
FRIGATE_API_TOKEN=replace-me
```

The internal unauthenticated API on port `5000` is also supported when
the token is omitted. That port grants broad access and must only be
used on a trusted, isolated container network.

Camera health expectations are live-reloaded from
`config/policies.yaml`:

```yaml
frigate:
  stalled_camera_severity: warning
  cameras:
    front:
      expected: active
      minimum_camera_fps: 5
      minimum_process_fps: 5
    retired_camera:
      expected: inactive
```

Active cameras are reported when they are missing, stop producing or
processing frames, or fall below their configured FPS minimum.
Inactive cameras are excluded from health findings. Unlisted cameras
retain the safe default check for zero capture or processing FPS.
Severity accepts `info`, `warning`, or `critical`; informational
findings do not reduce the Atlas health score.

---

### Obsidian provider

Mount the vault read-only into Atlas Core and add it to
`inventory/services.yaml`:

```yaml
services:
  obsidian:
    name: Obsidian
    vault_path: /vaults/atlas
    critical: false
    max_scan_files: 10000
    stale_after_days: 30
    exclude_directories:
      - .obsidian
      - .trash
```

The vault path must be absolute. Atlas reads filesystem metadata only;
note contents and full local paths are not returned by the provider.
The bounded scan reports Markdown note count, attachment count, newest
note modification time, and whether the file limit truncated the scan.
Symlinked files and directories are skipped to keep collection inside
the configured vault.

`stale_after_days` is optional. When configured, an old newest-note
timestamp creates an informational finding without reducing health.
Missing vaults, empty vaults, and truncated scans produce operational
findings.

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
- Proxmox, Docker, Home Assistant, Ollama, OPNsense, Frigate, and Obsidian
  integration
- Ollama model lifecycle operations
- Live Mission Control service health
- Provider-backed operational actions
- Operations workspace and action audit visibility
- JSON and CSV audit export
- Confirmed retention maintenance
- Provider and UTC date-range audit filtering
- Filter-aware audit exports
- Paginated audit results
- Audit detail views with shareable deep links
- Action and request-ID search
- 200 Atlas Core tests
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
