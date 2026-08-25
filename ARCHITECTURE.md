# Atlas OS Architecture — v0.15 candidate

## Released production topology

`compose.production.yaml` is the base production source of truth:

```text
operator browser
  -> Mission Control
       -> Atlas Core
       -> Atlas Agent
            -> local repository execution backend (default)
            -> optional, separately gated isolated backend:
                 authenticated worker requests through relay
                      -> runsc-isolated execution worker
                           -> allowlisted egress proxy

one-shot stagers:
  atlas-agent-auth-stager
  atlas-execution-auth-stager
  atlas-core-agent-auth-stager
```

The base has nine services: `atlas-core`, `atlas-agent`,
`atlas-agent-auth-stager`, `atlas-execution-worker`,
`atlas-execution-worker-relay`, `atlas-execution-auth-stager`,
`atlas-core-agent-auth-stager`, `atlas-egress-proxy`, and `mission-control`.
`compose.https.yaml` removes Mission Control's host publication and adds
`atlas-edge` as authenticated TLS ingress. `compose.operator-auth.yaml`
enables Core-owned operator sessions. `compose.provider-intent-activated.yaml`
explicitly activates Provider Intent against an operator-selected database and
accepted legacy-import identity.

## Component responsibilities

### Atlas Edge

Atlas Edge is optional hardened HTTPS ingress. It terminates TLS, applies HTTP
Basic authentication as defense in depth, and proxies browser traffic. It does
not replace Core authentication or grant mutation authority.

### Mission Control

Mission Control serves the operator UI and proxies Core and Agent APIs. It
presents provider, policy, Discovery, operational, recovery, and engineering
workflow state; authoritative validation remains server-side.

### Atlas Core

Core owns typed APIs, provider loading, policies and findings, operator
sessions, Provider Intent, Discovery, operational lifecycle state, and durable
control-plane databases. It mounts the Docker socket read-only for released
observation needs and dispatches only the registered operational tuple.

### Atlas Agent

Agent owns approval-gated repository workflow orchestration, persistence,
verification, review, and local commit boundaries. Its released repository
execution intent is only `update-compose-stack`. Agent also independently
enforces the hardened operational capability it relays from Core.

### Authentication staging

Three one-shot services stage least-privilege files into dedicated volumes:
Codex credentials for Agent, the Agent-to-worker token, and the Core-to-Agent
operational dispatch token. Runtime services mount only the credentials they
need.

### Execution relay, worker, and egress proxy

Agent uses the local repository execution backend by default. The packaged
`atlas-execution-worker`, `atlas-execution-worker-relay`, `atlas-egress-proxy`,
and related authentication staging are default-disabled infrastructure for an
optional isolated backend that requires explicit, separately gated activation.
When activated, authenticated worker requests pass through the relay on a
segmented internal network. Authentication is enforced end-to-end by the
worker together with the allowed relay-peer boundary. The worker runs with
`runsc`, a read-only repository source, disposable workspaces, and dropped
capabilities; outbound access passes through an allowlisted Squid proxy.

## Four distinct side-effect surfaces

1. **Legacy provider actions.** Provider routes expose a separate guarded
   action surface implemented by individual providers and recorded in provider
   action history. This exists and must not be described as the hardened tuple.
2. **Provider Intent control-plane mutation.** An authenticated, explicitly
   activated Core surface changes identity-bound Proxmox QEMU
   `monitoring-policy` only. It neither performs provider actions nor grants
   operational execution.
3. **Hardened operational dispatch.** The exact released tuple is
   `restart-service / proxmox / qemu`. Core and Agent enforce it independently;
   durable planning, approval, target fingerprint revalidation, dispatch, and
   verification contracts apply.
4. **Repository candidate execution.** The exact released intent is
   `update-compose-stack`, executed only through the Agent candidate workflow.
   The Agent local backend is the production default; the isolated worker
   backend requires explicit, separately gated activation. It is not provider
   or operational dispatch.

No surface implies automatic remediation, approval, update, deployment,
rollback, or release publication.

## Provider Intent

Provider Intent is default-not-activated in the base file. Its overlay changes
that state only when the database path and expected legacy import ID are
provided. The schema-v2 store then owns Proxmox QEMU monitoring expectations.
Authority is limited to monitoring policy and requires the dedicated operator
permission; operational and provider-action permissions do not imply it.

## Discovery evidence, cache, and v0.15 image-grounding projection

Discovery's public API is GET-only. Curated catalog data remains authoritative;
dynamic facts and the rebuildable cache are evidence with freshness, conflict,
and provenance semantics. V0.14 adds internal exact DeploymentBinding, Compose
observation, grounding, and provenance composition. Image evidence is
informational/read-only and has no operational authority. The generic image
collector is shipped inactive with empty production registries.

V0.15 P1–P3 add a binding-driven local read-only grounding service,
`GET /api/v1/discovery/items/{item_id}/image-grounding`, and an advisory
Mission Control panel. The bounded panel presents status, release, deployment
binding, observed image, accepted evidence, source class, source identity, and
attestation time. It has no action controls and grants no deployment or
execution authority. P4's authoritative security/isolation/authority matrix is
complete; P5 exact-SHA closure evidence remains pending.

`atlas-v0.14.0` remains the latest released Atlas version. V0.15 P0–P4 are
complete, P5 is in progress, `atlas-v0.15.0` has not yet been created, and
v0.15 is not yet released.

## Backup and restore boundary

Backup/restore is explicit operator maintenance tooling over documented durable
state. It is not an Agent execution intent. Rebuildable Discovery cache is not
durable backup authority, and restore compatibility is validated rather than
inferred from prose.

## Historical note

Earlier releases and documents sometimes described Core plus Mission Control
as the whole runtime. That was accurate only for an earlier development stage;
it is not the v0.14 production architecture.
