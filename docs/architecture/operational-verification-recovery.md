# Operational verification and recovery

Atlas v0.7 P1.3 enables `restart-service` independently in Agent and Core and
registers exactly one production handler for `restart-service / proxmox /
qemu`. This document describes the durable, read-only reconciliation that
follows a successful or ambiguous dispatch with a Proxmox task UPID.

## Durable lifecycle

The approved request `expires_at` is the fixed, digest-bound verification
deadline. A dispatch with a valid UPID may transition through:

```text
succeeded or outcome_unknown
  -> verifying
  -> verified | verification_failed | target_replaced | outcome_unknown
```

An `outcome_unknown` verification result is terminal and immutable. It is not
silently converted to `verification_failed` and cannot trigger another
mutation. Requests without a UPID remain unknown and are not scheduled for
provider reconciliation.

At Core startup, `dispatching` becomes `outcome_unknown` without replay.
Unverified `succeeded`, UPID-bearing `outcome_unknown`, and interrupted
`verifying` entries schedule provider-specific read-only verification. Verified
and failed results are never reopened.

## Production least privilege

The configured Proxmox identity requires `VM.Audit` and `VM.PowerMgmt` only on
the approved `/vms/<VMID>` target. It must not receive `Sys.PowerMgmt`,
permission-management, broad `VM.Config.*`, cluster-root, or administrative
roles. Some Proxmox installations may additionally require narrowly scoped
read-only task access to inspect the UPID returned by Atlas; operators must add
that only when their Proxmox version requires it.

## One-shot sandbox harness

`scripts/atlas-operational-sandbox` is separate from production gates. It
requires:

- a mode-`0400` strict `OperationalDispatchRequest` JSON file;
- a mode-`0400`, expiring `SandboxAuthorization` JSON file binding exactly one
  node, VMID, request digest, and resource fingerprint;
- `maximum_attempts: 1` and purpose
  `approved-non-critical-qemu-graceful-restart`;
- a new non-production ledger path;
- an interactive confirmation phrase containing the node, VMID, and digest.

The harness prints the exact target and disruption before confirmation. It
constructs an in-process one-shot handler registry and intent set, records one
dispatch attempt, then performs only read-only verification. It does not alter
the Agent or Core production capability sets or registry.

The harness is evidence tooling, not the production workflow. Production uses
the Core ledger and registered handler through authenticated Agent dispatch;
sandbox ledgers and authorizations are never accepted by that path.

## Acceptance evidence

The 2026-08-14 normal-path acceptance recorded:

- one production ledger record;
- `claimed -> revalidated -> dispatching -> succeeded -> verifying -> verified`;
- one durable barrier crossing;
- one provider-operation capture and one dispatch result;
- successful UPID-backed verification with the VM and QMP running;
- an unchanged authoritative target fingerprint; and
- no replay during Agent lifecycle reconciliation.
