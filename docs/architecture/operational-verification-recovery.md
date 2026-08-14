# Operational verification and recovery

P1.3e keeps both operational execution intent sets empty and the production
handler registry empty. It adds only durable, read-only reconciliation after a
future successful or ambiguous dispatch that has a Proxmox task UPID.

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

## Production ACL inspection

The 2026-08-14 read-only inspection established that the configured Proxmox
identity can read QEMU configuration, current QEMU status, effective
permissions, node task listings, and has `VM.Audit` and `Sys.Audit`. It does not
have `VM.PowerMgmt`, `Sys.PowerMgmt`, or permission-management privileges. No
recent owned `qmreboot` UPID was available, so exact owned-task status access
remains unproven.

No ACL was changed. Live sandbox execution remains blocked until an operator
confirms a non-critical target and grants only the required VM-scoped
`VM.PowerMgmt` permission.

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

The harness must not be used until change control has approved the target as
non-critical and the operator has reviewed the generated immutable request and
authorization files.
