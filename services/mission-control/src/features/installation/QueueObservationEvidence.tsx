import { useEffect, useState } from "react";

import { getOneShotLiveEnqueue } from "../../api/oneShotLiveEnqueue";
import { createQueueObservation, listQueueObservations, queueObservationCreateFromOneShot, queueObservationIdempotencyKey } from "../../api/queueObservation";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotLiveEnqueueV1 } from "../../types/oneShotLiveEnqueue";
import type { QueueObservationBlockerV1, QueueObservationReceiptResultV1, QueueObservationReceiptV1 } from "../../types/queueObservation";
import { ControlledDequeueAdmissions } from "./ControlledDequeueAdmissions";

const CONFIRMATION = "Record evidence that this saved queue reference was checked. This does not read or remove queue work, contact or start a worker, or run anything.";

const BLOCKERS: Record<QueueObservationBlockerV1, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "An earlier review is missing",
    ownership_mismatch: "An earlier review belongs to a different operator",
    permission_scope_missing: "Your account does not have permission for this review",
    linkage_mismatch: "The earlier reviews do not match each other",
    fingerprint_mismatch: "A saved evidence identity does not match",
    evidence_stale: "An earlier review is out of date",
    evidence_expired: "An earlier review has expired",
    v042_enqueue_not_active: "The queue reference is no longer current",
    v042_enqueue_not_recorded: "The queue reference was not saved",
    queue_identity_mismatch: "The saved queue reference does not match",
    item_identity_mismatch: "The saved item reference does not match",
    receipt_evidence_invalid: "The queue receipt is missing or invalid",
    observation_malformed: "The observation evidence is incomplete or invalid",
    ambiguous_state: "Atlas could not confirm the observation result",
    executable_payload: "This item contains work that cannot be observed here",
    unsupported_authority: "The queue reference does not have the required safety limits",
    dequeue_not_defined: "A safe way to take work from a queue is not defined",
    queue_polling_not_defined: "A safe way to check a queue is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
};

export function QueueObservationEvidence({ candidateId, oneShot }: { candidateId: string; oneShot: OneShotLiveEnqueueV1 }) {
    const session = useOperatorSession();
    const [items, setItems] = useState<QueueObservationReceiptV1[] | null>(null);
    const [error, setError] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [blockedResult, setBlockedResult] = useState<QueueObservationReceiptResultV1 | null>(null);

    useEffect(() => {
        let current = true;
        listQueueObservations(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.v042_enqueue.enqueue_id === oneShot.enqueue_id)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, oneShot.enqueue_id]);

    const permissions = session.principal?.permissions ?? [];
    const mayCreate = oneShot.lifecycle === "active" && session.authenticated && permissions.includes("installation.execution.queue_observation.record") && permissions.includes("installation.execution.one_shot_live_enqueue.read");
    const record = async () => {
        if (!session.csrfToken || submitting) return;
        setSubmitting(true); setError(false); setBlockedResult(null);
        try {
            const source = await getOneShotLiveEnqueue(candidateId, oneShot.enqueue_id);
            if (!source.record || !source.status) throw new Error("missing v0.42 enqueue readback");
            const result = await createQueueObservation(candidateId, queueObservationCreateFromOneShot(source.record, source.status), session.csrfToken, queueObservationIdempotencyKey());
            if (result.record) {
                setItems((current) => [result.record!, ...(current ?? [])]);
                setConfirming(false);
            } else {
                setBlockedResult(result);
            }
        } catch { setError(true); }
        finally { setSubmitting(false); }
    };

    const observed = (items?.length ?? 0) > 0;
    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Queue observation">
        <h6 className="font-semibold">Queue observation</h6>
        <p className="mt-2 text-sm">Status: {observed ? "Recorded" : "Not yet recorded"}. This saves evidence that the empty queue reference was checked; it does not read or remove queue work or start a worker.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading queue observation…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Queue observation could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>Queue observation was not recorded.</p><p className="mt-1 text-xs">{BLOCKERS[blockedResult.error.error_code as QueueObservationBlockerV1] ?? "Atlas could not confirm the observation result."}</p></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No observation is saved for this queue reference.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Queue observation receipts">{items.map((item) => <Observation key={item.receipt_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review what will be recorded</button>}
        {mayCreate && confirming && <div aria-label="Queue observation evidence confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Confirm queue observation</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core checks the saved queue reference, item reference, and safety limits before recording this evidence.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Record observation</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-3 text-sm text-amber-200">A current queue reference and a signed-in account with review permission are required to record an observation.</p>}
    </section>;
}

function Observation({ item }: { item: QueueObservationReceiptV1 }) {
    const receipt = item.receipt_evidence;
    const observation = item.queue_observation;
    const enqueue = item.v042_enqueue;
    const status = isExpired(item.valid_until) ? "Expired queue observation" : "Observation recorded";
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status}</h6>
        <p className="mt-1">The saved queue reference was checked. This does not mean it contains work that can run.</p>
        <p className="mt-1">Saved {formatDateTime(item.recorded_at)} · Expires {formatDateTime(item.valid_until)}.</p>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Receipt and queue reference details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Receipt ID" value={item.receipt_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Queue item ID" value={enqueue.queue_item.queue_item_id} />
                <Value name="v0.42 enqueue ID" value={enqueue.enqueue_id} />
                <Value name="v0.42 enqueue fingerprint" value={enqueue.record_fingerprint.value} />
                <Value name="v0.42 enqueue status fingerprint" value={item.v042_enqueue_status.status_fingerprint.value} />
                <Value name="Queue identity fingerprint" value={receipt.queue_intake_reference_fingerprint.value} />
                <Value name="Item identity fingerprint" value={receipt.inert_queue_item_fingerprint.value} />
                <Value name="Enqueue receipt fingerprint" value={receipt.receipt_fingerprint.value} />
                <Value name="Observation fingerprint" value={observation.observation_fingerprint.value} />
                <Value name="Lineage fingerprint" value={item.lineage_fingerprint.value} />
                <Value name="Subject fingerprint" value={item.subject_fingerprint.value} />
                <Value name="Receipt record fingerprint" value={item.receipt_record_fingerprint.value} />
                <Value name="Inherited limits fingerprint" value={enqueue.inherited_limits.limits_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-medium">Why an observation cannot allow work to start</h6>
            <ul aria-label="Why an observation cannot allow work to start" className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}>{BLOCKERS[value]}</li>)}</ul>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Authority and record details</summary>
            <p className="mt-2 text-xs">The observation can be recorded once and cannot be replayed. The raw idempotency key and queue receipt are not saved.</p>
            <p className="mt-2 text-xs">Core owns and verifies the receipt evidence. Technical identifiers are shown here for review.</p>
            <dl aria-label="Queue observation fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Payload schema defined", "Payload constructed", "Payload serialized", "Executable payload allowed", "Live enqueue allowed", "Dequeue defined", "Dequeue allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue ack allowed", "Worker contact allowed", "Worker start allowed", "Execution start allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Container execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <ControlledDequeueAdmissions candidateId={item.candidate_record_id} observation={item} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
