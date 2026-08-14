# Proxmox QEMU graceful-restart contract

Atlas v0.7 P1.3 enables one closed provider-owned operational action:

```text
restart-service + proxmox + qemu
  -> proxmox-qemu-graceful-restart-v1
```

Agent and Core independently allow only `restart-service` at this operational
boundary. Core registers exactly one production handler tuple:
`restart-service / proxmox / qemu`. Planning capability, provider metadata, and
approval state never implicitly enable execution.

## Identity and action

Atlas binds a QEMU guest to an opaque versioned digest of its Proxmox node,
VMID, and QEMU `vmgenid`. A changed `vmgenid`, VMID, node, resource type, or
provider fingerprint invalidates the approved request. Guest names, display
labels, and IP addresses are not identity inputs.

The only mutation implemented by the disabled handler is Proxmox's QEMU
`status/reboot` operation. It requests a graceful guest shutdown and restart.
There is no reset, stop/start sequence, host reboot, LXC action, or retry after
an ambiguous provider response.

## Least-privilege API token

The dedicated Proxmox identity used by Atlas requires:

- `VM.Audit` on `/vms/<VMID>` to read QEMU configuration and current status.
- `VM.PowerMgmt` on `/vms/<VMID>` to request the graceful reboot.

Atlas polls only the UPID returned by its own reboot request. Depending on the
Proxmox version and API-token privilege-separation configuration, reading that
owned task may require `Sys.Audit` on `/nodes/<node>`. Operators must test owned
task-status access first and add that narrowly scoped read-only privilege only
when required. Do not grant `PVEAdmin`, cluster-root ACLs, `Sys.PowerMgmt`,
`VM.Config.*`, or permission-management privileges for this action.

Existing credentials are not modified automatically. Before enabling the
capability for a target, the release operator must confirm the configured
identity has only the required VM scope and, if necessary, narrowly scoped
task-read access.

## Authentication and approval boundary

Mission Control operator mutations require authenticated HTTPS, an exact
trusted origin, CSRF validation, and a Core-owned session with
`operational_intent:create`. Edge Basic authentication remains an independent
defense-in-depth layer. The browser does not call the internal dispatch API.

Agent dispatches only an immutable request whose ID, digest, candidate and plan
fingerprints, provider/resource tuple, target fingerprint, action mapping,
verification policy, and expiry exactly match the persisted
`OPERATIONAL_ACTION` approval. Agent-to-Core bearer authentication is separate
from the browser operator session.

## Verification

Success requires all of the following within the bounded verification window:

- the exact provider-resource fingerprint remains unchanged;
- the returned task UPID completes with `exitstatus=OK`;
- the same QEMU guest is observed in `running` state.

Identity replacement fails closed. A completed failed task or a successful task
whose guest does not return to running by the deadline is verification failure.
An unavailable or still-running task at the deadline is an unknown outcome.
Verification is read-only and never issues another reboot.

## Production acceptance

On 2026-08-14 the normal production workflow exercised this contract once for
the approved non-critical QEMU guest VM 110 (`Frigate`) on `vorex469`. The
provider accepted exactly one graceful reboot and returned one UPID. The durable
ledger recorded one dispatch barrier, one provider-operation capture, and one
dispatch result. Verification completed with the VM and QMP running, the
authoritative fingerprint unchanged, and no mutation replay.
