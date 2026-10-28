import { useEffect, useState } from "react";

import { createControlledDequeueAdmission, controlledDequeueAdmissionCreateFromObservation, controlledDequeueAdmissionIdempotencyKey, listControlledDequeueAdmissions } from "../../api/controlledDequeueAdmission";
import { getQueueObservation } from "../../api/queueObservation";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ControlledDequeueAdmissionBlockerV1, ControlledDequeueAdmissionResultV1, ControlledDequeueAdmissionV1 } from "../../types/controlledDequeueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { QueueObservationReceiptV1 } from "../../types/queueObservation";
import { OneShotControlledDequeues } from "./OneShotControlledDequeues";

const CONFIRMATION = "Save evidence that a later queue handoff review may be considered. This does not take work from the queue, contact or start a worker, or run installation.";

const BLOCKERS: Record<ControlledDequeueAdmissionBlockerV1, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "An earlier review is missing",
    ownership_mismatch: "An earlier review belongs to a different operator",
    permission_scope_missing: "Your account does not have permission for this review",
    v043_observation_not_active: "The queue observation is no longer current",
    v043_observation_not_recorded: "The queue observation was not saved",
    v043_receipt_not_contract_eligible: "The queue observation receipt cannot be used for this review",
    v042_enqueue_not_active: "The queue reference is no longer current",
    v042_enqueue_not_recorded: "The queue reference was not saved",
    linkage_mismatch: "The earlier reviews do not match each other",
    queue_identity_mismatch: "The saved queue reference does not match",
    item_identity_mismatch: "The saved item reference does not match",
    observation_receipt_mismatch: "The observation receipt does not match this queue reference",
    fingerprint_mismatch: "A saved evidence identity does not match",
    inherited_limits_mismatch: "The safety limits do not match the earlier review",
    evidence_stale: "An earlier review is out of date",
    evidence_expired: "An earlier review has expired",
    ambiguous_state: "Atlas could not confirm the result",
    executable_payload: "This item contains work that cannot be reviewed here",
    unsupported_authority: "The queue reference does not have the required safety limits",
    reservation_before_effect_failed: "The save was blocked before an admission was created",
    permanent_subject_reserved: "An admission is already saved for this queue reference",
    idempotency_conflict: "A conflicting save request was received",
    append_indeterminate: "Atlas could not confirm whether the save finished",
    dequeue_not_defined: "A safe way to take work from a queue is not defined",
    queue_polling_not_defined: "A safe way to check a queue is not defined",
    queue_claim_not_defined: "A safe way to reserve work from a queue is not defined",
    queue_lease_not_defined: "A safe way to hold work from a queue is not defined",
    queue_ack_not_defined: "A safe way to confirm queue work is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
};

export function ControlledDequeueAdmissions({ candidateId, observation }: { candidateId: string; observation: QueueObservationReceiptV1 }) {
    const session = useOperatorSession();
    const [items, setItems] = useState<ControlledDequeueAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [blockedResult, setBlockedResult] = useState<ControlledDequeueAdmissionResultV1 | null>(null);

    useEffect(() => {
        let current = true;
        listControlledDequeueAdmissions(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.queue_observation_receipt.receipt_id === observation.receipt_id)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, observation.receipt_id]);

    const permissions = session.principal?.permissions ?? [];
    const mayCreate = observation.lifecycle === "active"
        && session.authenticated
        && permissions.includes("installation.execution.controlled_dequeue_admission.record")
        && permissions.includes("installation.execution.controlled_dequeue_admission.read")
        && permissions.includes("installation.execution.queue_observation.read");

    const record = async () => {
        if (!session.csrfToken || submitting) return;
        setSubmitting(true); setError(false); setBlockedResult(null);
        try {
            const source = await getQueueObservation(candidateId, observation.receipt_id);
            if (!source.record || !source.status) throw new Error("missing v0.43 observation readback");
            const result = await createControlledDequeueAdmission(candidateId, controlledDequeueAdmissionCreateFromObservation(source.record, source.status), session.csrfToken, controlledDequeueAdmissionIdempotencyKey());
            if (result.record) {
                setItems((current) => [result.record!, ...(current ?? [])]);
                setConfirming(false);
            } else {
                setBlockedResult(result);
            }
        } catch { setError(true); }
        finally { setSubmitting(false); }
    };

    const admitted = (items?.length ?? 0) > 0;
    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Dequeue readiness review">
        <h6 className="font-semibold">Dequeue readiness review</h6>
        <p className="mt-2 text-sm">Status: {admitted ? "Admission recorded" : "Not yet recorded"}. This saves readiness evidence only; it does not take work from a queue or start a worker.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading dequeue readiness reviews…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Dequeue readiness reviews could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>Admission was not recorded.</p><p className="mt-1 text-xs">{blockerMessage(blockedResult.error.error_code)}</p></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No readiness review is saved for this queue observation.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Controlled dequeue admissions">{items.map((item) => <Admission key={item.admission_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review what will be recorded</button>}
        {mayCreate && confirming && <div aria-label="Controlled dequeue admission confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Confirm dequeue readiness review</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core checks the saved observation, queue reference, and inherited safety limits before recording this review.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Save readiness review</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-3 text-sm text-amber-200">A current queue observation and a signed-in account with review permission are required to save this readiness review.</p>}
    </section>;
}

function Admission({ item }: { item: ControlledDequeueAdmissionV1 }) {
    const status = isExpired(item.valid_until) ? "Expired readiness review" : "Admission recorded";
    const receipt = item.queue_observation_receipt;
    const queueItem = receipt.v042_enqueue.queue_item;
    const limits = item.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status}</h6>
        <p className="mt-1">This record does not take work from the queue or start a worker.</p>
        <p className="mt-1">Saved {formatDateTime(item.recorded_at)} · Expires {formatDateTime(item.valid_until)}.</p>
        <h6 className="mt-3 font-medium">Why work cannot be taken</h6>
        <ul aria-label="Why work cannot be taken" className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}>{BLOCKERS[value]}</li>)}</ul>
        <h6 className="mt-3 font-medium">Limits recorded for a future worker</h6>
        <ul aria-label="Limits recorded for a future worker" className="mt-2 list-disc pl-5 text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Queue and review details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Admission ID" value={item.admission_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Queue observation receipt ID" value={receipt.receipt_id} />
                <Value name="Queue observation receipt fingerprint" value={receipt.receipt_record_fingerprint.value} />
                <Value name="Queue observation status fingerprint" value={item.queue_observation_receipt_status.status_fingerprint.value} />
                <Value name="v0.42 enqueue ID" value={receipt.v042_enqueue.enqueue_id} />
                <Value name="Queue item ID" value={queueItem.queue_item_id} />
                <Value name="Inert queue item fingerprint" value={queueItem.item_fingerprint.value} />
                <Value name="Queue identity fingerprint" value={item.queue_identity_fingerprint.value} />
                <Value name="Item identity fingerprint" value={item.item_identity_fingerprint.value} />
                <Value name="Lineage fingerprint" value={item.lineage_fingerprint.value} />
                <Value name="Subject fingerprint" value={item.subject_fingerprint.value} />
                <Value name="Admission record fingerprint" value={item.admission_record_fingerprint.value} />
                <Value name="Admission decision fingerprint" value={item.admission_decision.decision_fingerprint.value} />
                <Value name="Inherited limits fingerprint" value={item.inherited_limits.limits_fingerprint.value} />
                <Value name="Admission state code" value={item.admission_state} />
                <Value name="Eligibility code" value={item.eligibility} />
                <Value name="Disposition code" value={item.disposition} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Exact safety and authority details</summary>
            <h6 className="mt-2 font-medium">Inherited limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privilege escalation, host namespaces, devices" value="false" />
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
            <p className="mt-3 text-xs">This admission cannot be replayed. The raw idempotency key is not saved.</p>
            <p className="mt-2 text-xs">Audit events are bounded to the admission record, its read, and an indeterminate result. Core owns the audit details.</p>
            <dl aria-label="Controlled dequeue admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Payload schema defined", "Payload constructed", "Payload serialized", "Executable payload allowed", "Dequeue defined", "Dequeue allowed", "Dequeue attempted", "Dequeued", "Queue polling allowed", "Queue polled", "Queue claim allowed", "Queue claimed", "Queue lease allowed", "Queue leased", "Queue ack allowed", "Queue acked", "Queue consumed", "Worker contact allowed", "Worker contacted", "Worker start allowed", "Worker started", "Agent invocation allowed", "Execution start allowed", "Process execution allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Scheduler allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Container execution allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <OneShotControlledDequeues candidateId={item.candidate_record_id} admission={item} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function blockerMessage(code: string) { return Object.prototype.hasOwnProperty.call(BLOCKERS, code) ? BLOCKERS[code as ControlledDequeueAdmissionBlockerV1] : "Atlas could not confirm the result."; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
