import { useEffect, useState } from "react";

import { getControlledDequeueAdmission } from "../../api/controlledDequeueAdmission";
import { createOneShotControlledDequeue, listOneShotControlledDequeues, oneShotControlledDequeueCreateFromAdmission, oneShotControlledDequeueIdempotencyKey } from "../../api/oneShotControlledDequeue";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ControlledDequeueAdmissionV1 } from "../../types/controlledDequeueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotControlledDequeueBlockerV1, OneShotControlledDequeueResultV1, OneShotControlledDequeueV1 } from "../../types/oneShotControlledDequeue";
import { OneShotDequeueWorkerBindings } from "./OneShotDequeueWorkerBindings";

const CONFIRMATION = "Core will attempt to remove only the exact empty queue reference admitted here. It will not read task content or start a worker or installation. If the result is uncertain, do not repeat this action.";

const BLOCKERS: Record<OneShotControlledDequeueBlockerV1, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "An earlier review is missing",
    ownership_mismatch: "An earlier review belongs to a different operator",
    permission_scope_missing: "Your account does not have permission for this review",
    v044_admission_not_active: "The dequeue readiness review is no longer current",
    v044_admission_not_recorded: "The dequeue readiness review was not saved",
    v044_admission_not_eligible: "The dequeue readiness review cannot be used",
    v043_observation_not_active: "The queue observation is no longer current",
    v043_observation_not_recorded: "The queue observation was not saved",
    v043_receipt_not_contract_eligible: "The queue observation receipt cannot be used",
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
    executable_payload: "This item contains work that cannot be removed here",
    unsupported_authority: "The queue reference does not have the required safety limits",
    dequeue_adapter_unavailable: "No safe removal method is available for this queue",
    dequeue_receipt_mismatch: "The removal receipt does not match this reference",
    reservation_before_effect_failed: "Removal was blocked before a queue change was made",
    permanent_subject_reserved: "A removal attempt is already recorded for this reference",
    idempotency_conflict: "A conflicting removal request was received",
    append_indeterminate: "Atlas could not confirm whether the receipt was saved",
    dequeue_indeterminate: "Atlas could not confirm whether the reference was removed",
    queue_polling_not_defined: "A safe way to check a queue is not defined",
    queue_claim_not_defined: "A safe way to reserve queue work is not defined",
    queue_lease_not_defined: "A safe way to hold queue work is not defined",
    queue_ack_not_defined: "A safe way to confirm queue work is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
};

export function OneShotControlledDequeues({ candidateId, admission }: { candidateId: string; admission: ControlledDequeueAdmissionV1 }) {
    const session = useOperatorSession();
    const [items, setItems] = useState<OneShotControlledDequeueV1[] | null>(null);
    const [error, setError] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [blockedResult, setBlockedResult] = useState<OneShotControlledDequeueResultV1 | null>(null);

    useEffect(() => {
        let current = true;
        listOneShotControlledDequeues(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.controlled_dequeue_admission.admission_id === admission.admission_id)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, admission.admission_id]);

    const permissions = session.principal?.permissions ?? [];
    const mayCreate = admission.lifecycle === "active"
        && session.authenticated
        && permissions.includes("installation.execution.one_shot_controlled_dequeue.record")
        && permissions.includes("installation.execution.one_shot_controlled_dequeue.read")
        && permissions.includes("installation.execution.controlled_dequeue_admission.read");

    const record = async () => {
        if (!session.csrfToken || submitting) return;
        setSubmitting(true); setError(false); setBlockedResult(null);
        try {
            const source = await getControlledDequeueAdmission(candidateId, admission.admission_id);
            if (!source.record || !source.status) throw new Error("missing v0.44 admission readback");
            const result = await createOneShotControlledDequeue(candidateId, oneShotControlledDequeueCreateFromAdmission(source.record, source.status), session.csrfToken, oneShotControlledDequeueIdempotencyKey());
            if (result.record) {
                setItems((current) => [result.record!, ...(current ?? [])]);
                setConfirming(false);
            } else {
                setBlockedResult(result);
            }
        } catch { setError(true); }
        finally { setSubmitting(false); }
    };

    const latest = items?.[0] ?? null;
    const state = error
        ? "Receipt unavailable"
        : latest
        ? latest.disposition === "exact_inert_item_dequeued"
            ? "Reference removed"
            : latest.disposition === "exact_inert_item_not_dequeued"
              ? "Reference not removed"
              : "Removal result uncertain"
        : blockedResult?.outcome === "indeterminate"
          ? "Removal result uncertain"
          : blockedResult
            ? "Removal blocked"
            : "Not attempted";

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="One-time queue reference removal">
        <h6 className="font-semibold">One-time queue reference removal</h6>
        <p className="mt-2 text-sm">State: {state}. If confirmed, only the exact admitted empty reference was removed. No task content is read or worker started.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading removal receipts…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Removal receipts could not be loaded.</p><p className="mt-1 text-xs">If a removal was just attempted, do not repeat it until the result is checked. Technical error details are hidden.</p></div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>{blockedResult.outcome === "indeterminate" ? "The removal result is uncertain. Do not repeat this action." : "Removal did not complete."}</p><p className="mt-1 text-xs">{blockerMessage(blockedResult.error.error_code)}</p></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No removal receipt is saved for this admission.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Queue reference removal receipts">{items.map((item) => <Receipt key={item.dequeue_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review queue reference removal</button>}
        {mayCreate && confirming && <div aria-label="One-shot controlled dequeue confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Confirm one-time queue reference removal</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core verifies the exact admission and queue reference before attempting removal. An uncertain result cannot be safely repeated.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Remove exact reference</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-3 text-sm text-amber-200">A current admission and a signed-in account with permission are required to remove this queue reference.</p>}
    </section>;
}

function Receipt({ item }: { item: OneShotControlledDequeueV1 }) {
    const result = item.disposition === "exact_inert_item_dequeued"
        ? "Queue reference removed"
        : item.disposition === "exact_inert_item_not_dequeued"
          ? "Queue reference not removed"
          : "Removal result uncertain";
    const status = isExpired(item.valid_until) ? `Expired receipt · ${result}` : result;
    const admission = item.controlled_dequeue_admission;
    const observation = admission.queue_observation_receipt;
    const enqueue = observation.v042_enqueue;
    const bounded = item.bounded_receipt;
    const limits = item.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status}</h6>
        <p className="mt-1">This receipt covers only the exact queue reference approved for removal. It does not start a worker or installation.</p>
        <p className="mt-1">Saved {formatDateTime(item.recorded_at)} · Expires {formatDateTime(item.valid_until)}.</p>
        <h6 className="mt-3 font-medium">Limits recorded for a future worker</h6>
        <ul aria-label="Limits recorded for a future worker" className="mt-2 list-disc pl-5 text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Queue and receipt details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Dequeue ID" value={item.dequeue_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Controlled dequeue admission" value={admission.admission_id} />
                <Value name="Controlled dequeue admission fingerprint" value={admission.admission_record_fingerprint.value} />
                <Value name="Controlled dequeue admission status fingerprint" value={item.controlled_dequeue_admission_status.status_fingerprint.value} />
                <Value name="Queue observation receipt" value={observation.receipt_id} />
                <Value name="Queue observation receipt fingerprint" value={observation.receipt_record_fingerprint.value} />
                <Value name="Queue observation status fingerprint" value={admission.queue_observation_receipt_status.status_fingerprint.value} />
                <Value name="v0.42 enqueue ID" value={enqueue.enqueue_id} />
                <Value name="Queue item ID" value={enqueue.queue_item.queue_item_id} />
                <Value name="Queue identity fingerprint" value={item.queue_identity_fingerprint.value} />
                <Value name="Item identity fingerprint" value={item.item_identity_fingerprint.value} />
                <Value name="Lineage fingerprint" value={item.lineage_fingerprint.value} />
                <Value name="Subject fingerprint" value={item.subject_fingerprint.value} />
                <Value name="Dequeue record fingerprint" value={item.dequeue_record_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint.value} />
                <Value name="Adapter receipt fingerprint" value={bounded.adapter_receipt_fingerprint.value} />
                <Value name="Bounded receipt fingerprint" value={bounded.receipt_fingerprint.value} />
                <Value name="Removal result code" value={item.disposition} />
                <Value name="Dequeue state code" value={item.dequeue_state} />
                <Value name="Adapter receipt redacted" value="true" />
                <Value name="Exact admitted reference only" value="true" />
            </dl>
            <h6 className="mt-3 font-medium">Further actions still unavailable</h6>
            <ul aria-label="Further actions still unavailable" className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}>{BLOCKERS[value]}</li>)}</ul>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Exact safety and authority details</summary>
            <h6 className="mt-2 font-medium">Inherited limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privilege, escalation, host namespaces, devices" value="false" />
                <Value name="Drop all capabilities" value="true" />
                <Value name="Seccomp and AppArmor required" value="true" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
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
            <p className="mt-3 text-xs">The removal attempt cannot be repeated. The raw idempotency key and adapter receipt are not saved.</p>
            <p className="mt-2 text-xs">Core owns the receipt and audit evidence. Technical identifiers are shown here for review.</p>
            <dl aria-label="One-shot controlled dequeue fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Payload schema defined", "Payload constructed", "Payload serialized", "Executable payload allowed", "Dequeue defined", "Dequeue allowed", "Queue polling allowed", "Queue polled", "Queue claim allowed", "Queue claimed", "Queue lease allowed", "Queue leased", "Queue ack allowed", "Queue acked", "Queue consumed", "Worker contact allowed", "Worker contacted", "Worker start allowed", "Worker started", "Agent invocation allowed", "Execution start allowed", "Process execution allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Scheduler allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Container execution allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <OneShotDequeueWorkerBindings candidateId={item.candidate_record_id} dequeueId={item.dequeue_id} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function blockerMessage(code: string) { return Object.prototype.hasOwnProperty.call(BLOCKERS, code) ? BLOCKERS[code as OneShotControlledDequeueBlockerV1] : "Atlas could not confirm the removal result."; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
