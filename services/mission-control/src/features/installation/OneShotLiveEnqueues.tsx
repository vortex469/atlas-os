import { useEffect, useState } from "react";

import { listOneShotLiveEnqueues } from "../../api/oneShotLiveEnqueue";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotLiveEnqueueBlockerV1, OneShotLiveEnqueueV1 } from "../../types/oneShotLiveEnqueue";
import { QueueObservationEvidence } from "./QueueObservationEvidence";

const BLOCKERS: Record<OneShotLiveEnqueueBlockerV1, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "An earlier review is missing",
    ownership_mismatch: "An earlier review belongs to a different operator",
    permission_scope_missing: "Your account does not have permission for this review",
    linkage_mismatch: "The earlier reviews do not match each other",
    fingerprint_mismatch: "A saved evidence identity does not match",
    evidence_stale: "An earlier review is out of date",
    evidence_expired: "An earlier review has expired",
    live_enqueue_admission_not_active: "The queue handoff review is no longer current",
    live_enqueue_admission_not_recorded: "The queue handoff review was not saved",
    queue_reservation_not_active: "The queue reservation is no longer current",
    worker_intake_admission_not_active: "The worker intake review is no longer current",
    worker_identity_ineligible: "The worker reference cannot be used for this review",
    worker_intake_reference_ineligible: "The intake reference cannot be used for this review",
    queue_intake_reference_ineligible: "The queue reference cannot be used for this review",
    queue_item_reference_ineligible: "The item reference cannot be used for this review",
    inherited_limits_mismatch: "The safety limits do not match the earlier review",
    reservation_before_effect_failed: "The save was blocked before a queue reference was created",
    permanent_subject_reserved: "A queue reference is already saved for this review",
    idempotency_conflict: "A conflicting save request was received",
    append_indeterminate: "Atlas could not confirm whether the save finished",
    dequeue_not_defined: "A safe way to take work from a queue is not defined",
    queue_polling_not_defined: "A safe way to check a queue is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
};

export function OneShotLiveEnqueues({ candidateId, liveEnqueueAdmissionId, homeAssistantBlocked }: { candidateId: string; liveEnqueueAdmissionId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<OneShotLiveEnqueueV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listOneShotLiveEnqueues(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.lineage.live_enqueue_admission_id === liveEnqueueAdmissionId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, liveEnqueueAdmissionId]);

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Saved queue references">
        <h6 className="font-semibold">Queue reference</h6>
        <p className="mt-2 text-sm">Core saved a reference for a possible queue item. It contains no work payload; saving it does not send work or start a worker.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">Atlas cannot install Home Assistant, so it cannot be prepared for a worker.</p>}
        {items === null && !error && <p role="status" className="mt-3">Loading saved queue references…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Saved queue references could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No queue reference is saved. No work has been sent or started.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Saved queue references">{items.map((item) => <OneShot key={item.enqueue_id} item={item} />)}</ol>}
    </section>;
}

function OneShot({ item }: { item: OneShotLiveEnqueueV1 }) {
    const status = isExpired(item.valid_until) ? "Expired queue reference" : "Saved queue reference";
    const lineage = item.lineage;
    const queueItem = item.queue_item;
    const limits = item.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status}</h6>
        <p className="mt-1">This is only a reference for a possible queue item. It cannot be read as work or run.</p>
        <p className="mt-1">Saved {formatDateTime(item.recorded_at)} · Expires {formatDateTime(item.valid_until)}.</p>
        <h6 className="mt-3 font-medium">Why it cannot run</h6>
        <ul aria-label="Why this queue reference cannot run" className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}>{BLOCKERS[value]}</li>)}</ul>
        <h6 className="mt-3 font-medium">Safety limits recorded for a future worker</h6>
        <ul aria-label="Safety limits recorded for a future worker" className="mt-2 list-disc pl-5 text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Queue item and earlier reviews</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Enqueue ID" value={item.enqueue_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Queue item ID" value={queueItem.queue_item_id} />
                <Value name="Item kind code" value={queueItem.item_kind} />
                <Value name="Live enqueue admission ID" value={lineage.live_enqueue_admission_id} />
                <Value name="Worker intake admission ID" value={lineage.worker_intake_admission_id} />
                <Value name="Queue reservation ID" value={lineage.queue_reservation_id} />
                <Value name="Queue item reference ID" value={lineage.queue_item_reference_id} />
                <Value name="Lifecycle code" value={item.lifecycle} />
                <Value name="Outcome code" value={item.outcome} />
                <Value name="Record fingerprint" value={item.record_fingerprint.value} />
                <Value name="Item subject fingerprint" value={item.item_subject_fingerprint.value} />
                <Value name="Request fingerprint" value={item.request_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint.value} />
                <Value name="Item fingerprint" value={queueItem.item_fingerprint.value} />
                <Value name="Lineage fingerprint" value={lineage.lineage_fingerprint.value} />
                <Value name="v0.20-v0.41 chain fingerprint" value={lineage.v020_v041_chain_fingerprint.value} />
                <Value name="Live enqueue admission fingerprint" value={lineage.live_enqueue_admission_fingerprint.value} />
                <Value name="Live enqueue admission status fingerprint" value={lineage.live_enqueue_admission_status_fingerprint.value} />
                <Value name="Worker intake admission fingerprint" value={lineage.worker_intake_admission_fingerprint.value} />
                <Value name="Queue reservation fingerprint" value={lineage.queue_reservation_fingerprint.value} />
                <Value name="Queue intake reference fingerprint" value={lineage.queue_intake_reference_fingerprint.value} />
                <Value name="Queue item reference fingerprint" value={lineage.queue_item_reference_fingerprint.value} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Exact safety limits and record details</summary>
            <h6 className="mt-2 font-medium">Exact sandbox and resource limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privilege, escalation, host namespaces, devices" value="false" />
                <Value name="Drop all capabilities" value="true" />
                <Value name="Seccomp and AppArmor required" value="true" />
                <Value name="CPU ceiling (millicores)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Wall-time ceiling (seconds)" value={String(limits.resources.wall_time_seconds_max)} />
                <Value name="Output ceiling (bytes)" value={String(limits.resources.output_bytes_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Ingress, egress, DNS, image pull" value="false" />
                <Value name="Root filesystem read only" value="true" />
                <Value name="Host, repository, and guest mounts" value="false" />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Temporary workspace ceiling (bytes)" value={String(limits.filesystem.ephemeral_workspace_bytes_max)} />
                <Value name="Inherited limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-medium">Earlier evidence linked to this record</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Live enqueue review fingerprint" value={lineage.live_enqueue_admission_fingerprint.value} />
                <Value name="Live enqueue review status fingerprint" value={lineage.live_enqueue_admission_status_fingerprint.value} />
                <Value name="Worker intake review fingerprint" value={lineage.worker_intake_admission_fingerprint.value} />
                <Value name="Queue reservation fingerprint" value={lineage.queue_reservation_fingerprint.value} />
                <Value name="Queue reference fingerprint" value={lineage.queue_item_reference_fingerprint.value} />
                <Value name="Worker reference fingerprint" value={lineage.worker_identity_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">This reference cannot be retried, resent, or replayed. The raw idempotency key is not saved.</p>
            <p className="mt-2 text-xs">Audit evidence is server-owned and fingerprint-bound. Technical identifiers are shown here for review.</p>
            <dl aria-label="One-shot live enqueue fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Payload schema defined", "Payload constructed", "Payload serialized", "Dequeue defined", "Dequeue allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue ack allowed", "Worker contact allowed", "Worker authentication allowed", "Worker binding allowed", "Worker start allowed", "Execution start allowed", "Runner binding allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Scheduler allowed", "Docker execution allowed", "Podman execution allowed", "Container execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <QueueObservationEvidence candidateId={item.candidate_record_id} oneShot={item} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
