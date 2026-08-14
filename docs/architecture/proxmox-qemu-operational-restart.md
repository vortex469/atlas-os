# Proxmox QEMU graceful-restart contract

Atlas P1.3d defines, but does not enable, one provider-owned operational action:

```text
restart-service + proxmox + qemu
  -> proxmox-qemu-graceful-restart-v1
```

Both Agent and Core operational execution intent sets remain empty, and the
production operational handler registry remains empty. This contract therefore
cannot perform a production mutation in P1.3d.

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

Existing credentials are not modified automatically. Before future execution
enablement, the release operator must confirm the token has only the required
VM and, if necessary, node-read scope.

## Verification

Success requires all of the following within the bounded verification window:

- the exact provider-resource fingerprint remains unchanged;
- the returned task UPID completes with `exitstatus=OK`;
- the same QEMU guest is observed in `running` state.

Identity replacement fails closed. A completed failed task or a successful task
whose guest does not return to running by the deadline is verification failure.
An unavailable or still-running task at the deadline is an unknown outcome.
Verification is read-only and never issues another reboot.
