import { useEffect, useState } from "react";

import { createControlledDequeueAdmission, controlledDequeueAdmissionCreateFromObservation, controlledDequeueAdmissionIdempotencyKey, listControlledDequeueAdmissions } from "../../api/controlledDequeueAdmission";
import { getQueueObservation } from "../../api/queueObservation";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ControlledDequeueAdmissionResultV1, ControlledDequeueAdmissionV1 } from "../../types/controlledDequeueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { QueueObservationReceiptV1 } from "../../types/queueObservation";
import { OneShotControlledDequeues } from "./OneShotControlledDequeues";

const CONFIRMATION = "Record controlled dequeue admission evidence only. This does not dequeue, poll, claim, lease, acknowledge, consume, remove, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything.";

const BLOCKERS: Record<string, string> = {
    installation_capability_unsupported: "This type of installation is not supported.",
    evidence_not_found: "Required review information is missing.",
    ownership_mismatch: "This record belongs to a different owner.",
    permission_scope_missing: "The required permission is missing.",
    v043_observation_not_active: "The queue receipt review is no longer current.",
    v043_observation_not_recorded: "The queue receipt review record is missing.",
    v043_receipt_not_contract_eligible: "The queue receipt could not be verified.",
    v042_enqueue_not_active: "The queue item is no longer current.",
    v042_enqueue_not_recorded: "The queue item record is missing.",
    linkage_mismatch: "The linked records do not match.",
    queue_identity_mismatch: "The queue reference does not match.",
    item_identity_mismatch: "The item reference does not match.",
    observation_receipt_mismatch: "The queue receipt does not match the saved observation.",
    fingerprint_mismatch: "A record integrity check did not pass.",
    inherited_limits_mismatch: "The worker limits do not match the reviewed limits.",
    evidence_stale: "Some review information is out of date.",
    evidence_expired: "Some review information has expired.",
    ambiguous_state: "Atlas cannot confirm the current status.",
    executable_payload: "This item is not a supported inert reference.",
    unsupported_authority: "This request asks for more access than review permits.",
    permanent_subject_reserved: "A review record already exists for this request.",
    idempotency_conflict: "This request conflicts with a saved record.",
    append_indeterminate: "Atlas could not confirm the record outcome.",
    dequeue_not_defined: "Atlas has not set up a way to remove queued work.",
    queue_polling_not_defined: "Atlas has not set up a way to read work from a queue.",
    queue_claim_not_defined: "Atlas has not set up a way to claim queued work.",
    queue_lease_not_defined: "Atlas has not set up a way to reserve queued work.",
    queue_ack_not_defined: "Atlas has not set up a way to acknowledge queued work.",
    worker_start_not_defined: "Atlas has not set up a way to start a worker.",
    execution_start_boundary_not_defined: "Atlas has not set up a safe way to start this installation.",
};

export function ControlledDequeueAdmissions({ candidateId, observation }: { candidateId: string; observation: QueueObservationReceiptV1 }) {
    const session = useOperatorSession();
    const [items, setItems] = useState<ControlledDequeueAdmissionV1[] | null>(null);
    const [error, setError] = useState<"load" | "create" | null>(null);
    const [readAttempt, setReadAttempt] = useState(0);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [blockedResult, setBlockedResult] = useState<ControlledDequeueAdmissionResultV1 | null>(null);

    useEffect(() => {
        let current = true;
        listControlledDequeueAdmissions(candidateId)
            .then((value) => { if (current) { setItems(value.items.filter((item) => item.queue_observation_receipt.receipt_id === observation.receipt_id)); setError(null); } })
            .catch(() => { if (current) setError("load"); });
        return () => { current = false; };
    }, [candidateId, observation.receipt_id, readAttempt]);

    const permissions = session.principal?.permissions ?? [];
    const mayCreate = observation.lifecycle === "active"
        && items !== null && items.length === 0 && !error && blockedResult === null
        && session.authenticated
        && permissions.includes("installation.execution.controlled_dequeue_admission.record")
        && permissions.includes("installation.execution.controlled_dequeue_admission.read")
        && permissions.includes("installation.execution.queue_observation.read")
        && Boolean(session.csrfToken);

    const record = async () => {
        if (!session.csrfToken || submitting) return;
        setSubmitting(true); setError(null); setBlockedResult(null);
        try {
            const source = await getQueueObservation(candidateId, observation.receipt_id);
            if (!source.record || !source.status) throw new Error("missing v0.43 observation readback");
            const result = await createControlledDequeueAdmission(candidateId, controlledDequeueAdmissionCreateFromObservation(source.record, source.status), session.csrfToken, controlledDequeueAdmissionIdempotencyKey());
            if (result.record) {
                setItems((current) => [result.record!, ...(current ?? [])]);
                setConfirming(false);
            } else {
                setBlockedResult(result); setConfirming(false);
            }
        } catch { setError("create"); setConfirming(false); }
        finally { setSubmitting(false); }
    };

    const admitted = (items?.length ?? 0) > 0;
    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Controlled dequeue admission evidence">
        <h6 className="font-semibold">Queue removal review</h6>
        <p className="mt-2 text-sm">This saves a review record only. It does not remove work from the queue or start a worker.</p>
        {admitted && <p role="status" className="mt-2">A queue removal review record has been saved.</p>}
        {items === null && !error && <p role="status" className="mt-3">Checking for a saved queue removal review…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>{error === "load" ? "Atlas could not load the queue removal review. Retry to check its current status." : "Atlas could not confirm whether it saved the review record. This screen will not resend the request."}</p><p className="text-xs text-slate-400">Private system details are hidden.</p>{error === "load" && <button type="button" onClick={() => { setItems(null); setError(null); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button>}</div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>The queue removal review remains blocked.</p><p className="mt-1 text-sm">{BLOCKERS[blockedResult.error.error_code] ?? "Atlas reported an issue that needs review."}</p><details className="mt-2"><summary>Technical details</summary><p className="mt-2">Result: {blockedResult.outcome}; blocker code: <code>{blockedResult.error.error_code}</code>.</p></details></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No queue removal review has been saved for this receipt.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Saved queue removal reviews">{items.map((item) => <Admission key={item.admission_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review queue removal statement</button>}
        {mayCreate && confirming && <div aria-label="Controlled dequeue admission confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Step 2 of 2 — save the review record</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core ties this record to your account and the exact queue receipt. It cannot be replayed.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Save review record</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {items?.length === 0 && !error && !blockedResult && !mayCreate && <p className="mt-3 text-sm text-amber-200">Saving this review needs a current queue receipt, a signed-in operator with permission, and a valid session.</p>}
    </section>;
}

function Admission({ item }: { item: ControlledDequeueAdmissionV1 }) {
    const expired = isExpired(item.valid_until);
    const receipt = item.queue_observation_receipt;
    const queueItem = receipt.v042_enqueue.queue_item;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{expired ? "Queue removal review has expired" : "Queue removal review is current"}</p>
        <p className="mt-1">This record does not remove queued work or start a worker.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(item.recorded_at)}; valid until {formatUtcTimestamp(item.valid_until)}. An expired record cannot be renewed.</p>
        <ol aria-label="What needs attention" className="mt-2 list-decimal pl-5">{item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? "Atlas reported an issue that needs review."}</li>)}</ol>
        <details className="mt-3">
            <summary>Technical details</summary>
            <p className="mt-2">Record state: {item.admission_state}; eligibility: {item.eligibility}; result: {item.disposition}.</p>
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
            </dl>
            <details className="mt-3"><summary>Blocker codes</summary><ul className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}><code>{value}</code></li>)}</ul></details>
            <p className="mt-3 text-xs">Audit events are bounded to controlled_dequeue_admission_recorded, controlled_dequeue_admission_read, and controlled_dequeue_admission_indeterminate. Permanent subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false.</p>
            <p className="mt-2 text-xs">Mission Control shows only Core-supplied lineage, identifiers, fingerprints, ownership, freshness, blockers, admission status, and audit details; raw queue, broker, lease, acknowledgement, worker, command, and payload details are not displayed.</p>
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
function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
