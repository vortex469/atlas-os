# Atlas OS

Atlas OS is a local-first infrastructure control plane that turns provider,
inventory, policy, and Discovery evidence into operator-facing explanations,
recommendations, and tightly bounded approved actions.

## Current release

The current release is **Atlas v0.14.0**, published as `atlas-v0.14.0` at
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7` on 2026-08-24.

## What Atlas does today

Atlas Core collects and normalizes infrastructure state, evaluates policy,
serves the API, and owns durable control-plane state. Mission Control provides
the browser experience. Atlas Agent manages approval-gated engineering
workflows. Discovery Center supplies curated and dynamic read-only evidence,
compatibility and release intelligence, proposals, exact Compose image
observation, image grounding, and provenance.

Released mutation surfaces are deliberately separate:

- legacy provider actions exposed by individual providers;
- Provider Intent mutation, limited to Proxmox QEMU `monitoring-policy`;
- hardened operational dispatch, exactly `restart-service / proxmox / qemu`;
- repository candidate execution, exactly `update-compose-stack`.

## What Atlas deliberately does not do

Atlas does not automatically remediate, approve, update, deploy, roll back, or
publish releases. Discovery is GET-only/read-only. V0.14 image evidence and
grounding are informational and grant no operational authority. The generic
image collector is inactive: production descriptor and adapter registries are
empty and no startup or scheduled collection is wired.

## Architecture overview

```text
browser -> Mission Control -> Atlas Core -> providers / runtime state
                      |           |
                      v           v
                 Atlas Agent   operational dispatch
                      |
             local execution backend (default)
                      |
             optional, separately gated:
             authenticated worker requests through relay
                      -> isolated execution worker -> egress proxy
```

The optional HTTPS overlay puts Atlas Edge in front of Mission Control. See
[the canonical architecture](ARCHITECTURE.md).

## Production services

`compose.production.yaml` defines nine base services: `atlas-core`,
`atlas-agent`, `atlas-agent-auth-stager`, `atlas-execution-worker`,
`atlas-execution-worker-relay`, `atlas-execution-auth-stager`,
`atlas-core-agent-auth-stager`, `atlas-egress-proxy`, and `mission-control`.
Overlays add HTTPS/`atlas-edge`, Core-owned operator authentication, and
Provider Intent activation.

## Local development

Local development runs components directly and is not the production topology.
Atlas Core requires Python 3.12; Mission Control requires a supported Node.js
and npm toolchain. Typical startup:

```bash
cd services/atlas-core
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8643

cd ../mission-control
npm ci
npm run dev
```

The development server proxies API requests to Core. Atlas Agent and the
hardened execution path have their own development and test workflows.

## Production deployment

Production uses the hardened Compose package and persistent named volumes.
Agent defaults to its local repository execution backend. The package also
includes default-disabled worker, relay, egress-proxy, and related auth-staging
infrastructure for an isolated backend that requires explicit, separately gated
activation. Follow [Production Deployment](docs/DEPLOYMENT.md); do not infer
production layout from the two-process development example.

## Security / authority model

Core owns API contracts, operator sessions, Provider Intent, operational
dispatch, and Discovery state. Agent owns repository workflow orchestration and
independently enforces execution capabilities. Backup/restore is operator
maintenance tooling, never an Agent execution intent. Credentials remain
outside tracked configuration and side effects require the authority specific
to their surface.

## Release history links

- [Changelog](CHANGELOG.md)
- [Release checklist and evidence](docs/RELEASE_CHECKLIST.md)
- [Deployment and historical upgrade notes](docs/DEPLOYMENT.md)

## Roadmap link

See the [Atlas roadmap](ROADMAP.md). The selected v0.15 theme is
**Deployment Image Grounding Operator Surface**, a read-only operator-facing
surface over released image grounding; remaining future directions are
uncommitted.

The decision-complete P1–P5 plan is in the roadmap: reuse the released
binding/observation/evidence grounding chain, expose it through a redacted
GET-only Core projection, render it as advisory Mission Control information,
prove authority isolation and absence of startup, scheduled, and request-time
acquisition, and close with exact-SHA release gates plus read-only production
acceptance. A grounding/provenance GET uses only already-accepted local
evidence and reviewed local readers; it cannot trigger GHCR access, registry
acquisition, Sigstore verification, collector execution, or evidence refresh.
The plan adds no durable state, mutation, or execution authority.
