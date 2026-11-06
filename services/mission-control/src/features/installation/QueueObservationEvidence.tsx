import { useEffect, useState } from "react";

import { getOneShotLiveEnqueue } from "../../api/oneShotLiveEnqueue";
import { createQueueObservation, listQueueObservations, queueObservationCreateFromOneShot, queueObservationIdempotencyKey } from "../../api/queueObservation";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotLiveEnqueueV1 } from "../../types/oneShotLiveEnqueue";
import type { QueueObservationReceiptResultV1, QueueObservationReceiptV1 } from "../../types/queueObservation";
import { ControlledDequeueAdmissions } from "./ControlledDequeueAdmissions";

const CONFIRMATION = "Record bounded queue observation evidence only. This does not dequeue, poll as a consumer, claim, lease, acknowledge, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything.";

const BLOCKERS: Record<string, string> = {
    installation_capability_unsupported: "This type of installation is not supported.",
    evidence_not_found: "Required review information is missing.",
    ownership_mismatch: "This record belongs to a different owner.",
    permission_scope_missing: "The required permission is missing.",
    linkage_mismatch: "The linked records do not match.",
    fingerprint_mismatch: "A record integrity check did not pass.",
    evidence_stale: "Some review information is out of date.",
    evidence_expired: "Some review information has expired.",
    v042_enqueue_not_active: "The queue item is no longer current.",
    v042_enqueue_not_recorded: "The queue item record is missing.",
    queue_identity_mismatch: "The queue reference does not match.",
    item_identity_mismatch: "The item reference does not match.",
    receipt_evidence_invalid: "The queue receipt could not be verified.",
    observation_malformed: "The observation record is incomplete.",
    ambiguous_state: "Atlas cannot confirm the observation status.",
    executable_payload: "This item is not a supported inert reference.",
    unsupported_authority: "This request asks for more access than observation permits.",
    dequeue_not_defined: "Atlas has not set up a way to remove queued work.",
    queue_polling_not_defined: "Atlas has not set up a way to read work from a queue.",
    worker_start_not_defined: "Atlas has not set up a way to start a worker.",
    execution_start_boundary_not_defined: "Atlas has not set up a safe way to start this installation.",
};

export function QueueObservationEvidence({ candidateId, oneShot }: { candidateId: string; oneShot: OneShotLiveEnqueueV1 }) {
    const session = useOperatorSession();
    const [items, setItems] = useState<QueueObservationReceiptV1[] | null>(null);
    const [error, setError] = useState<"load" | "create" | null>(null);
    const [readAttempt, setReadAttempt] = useState(0);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [blockedResult, setBlockedResult] = useState<QueueObservationReceiptResultV1 | null>(null);

    useEffect(() => {
        let current = true;
        listQueueObservations(candidateId)
            .then((value) => { if (current) { setItems(value.items.filter((item) => item.v042_enqueue.enqueue_id === oneShot.enqueue_id)); setError(null); } })
            .catch(() => { if (current) setError("load"); });
        return () => { current = false; };
    }, [candidateId, oneShot.enqueue_id, readAttempt]);

    const permissions = session.principal?.permissions ?? [];
    const mayCreate = items !== null && items.length === 0 && !error && blockedResult === null &&
        oneShot.lifecycle === "active" && session.authenticated &&
        permissions.includes("installation.execution.queue_observation.record") &&
        permissions.includes("installation.execution.one_shot_live_enqueue.read") &&
        Boolean(session.csrfToken);
    const record = async () => {
        if (!session.csrfToken || submitting) return;
        setSubmitting(true); setError(null); setBlockedResult(null);
        try {
            const source = await getOneShotLiveEnqueue(candidateId, oneShot.enqueue_id);
            if (!source.record || !source.status) throw new Error("missing v0.42 enqueue readback");
            const result = await createQueueObservation(candidateId, queueObservationCreateFromOneShot(source.record, source.status), session.csrfToken, queueObservationIdempotencyKey());
            if (result.record) {
                setItems((current) => [result.record!, ...(current ?? [])]);
                setConfirming(false);
            } else {
                setBlockedResult(result); setConfirming(false);
            }
        } catch { setError("create"); setConfirming(false); }
        finally { setSubmitting(false); }
    };

    const observed = (items?.length ?? 0) > 0;
    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Queue observation and enqueue receipt evidence">
        <h6 className="font-semibold">Queue receipt review</h6>
        <p className="mt-2 text-sm">This saves Core-supplied receipt evidence only. It does not remove or process queued work.</p>
        {observed && <p role="status" className="mt-2">A queue receipt record has been saved.</p>}
        {items === null && !error && <p role="status" className="mt-3">Checking for a saved queue receipt…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>{error === "load" ? "Atlas could not load the queue receipt record. Retry to check its current status." : "Atlas could not confirm whether it saved the queue receipt record. This screen will not resend the request."}</p><p className="text-xs text-slate-400">Private system details are hidden.</p>{error === "load" && <button type="button" onClick={() => { setItems(null); setError(null); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button>}</div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>The queue receipt is still pending or blocked.</p><p className="mt-1 text-sm">{BLOCKERS[blockedResult.error.error_code] ?? "Atlas reported an issue that needs review."}</p><details className="mt-2"><summary>Technical details</summary><p className="mt-2">Result: {blockedResult.outcome}; blocker code: <code>{blockedResult.error.error_code}</code>.</p></details></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No queue receipt record has been saved for this item.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Queue observation receipts">{items.map((item) => <Observation key={item.receipt_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review receipt record statement</button>}
        {mayCreate && confirming && <div aria-label="Queue observation evidence confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Step 2 of 2 — save the receipt record</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core binds this record to your account and the exact queue item. It cannot be replayed.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Save receipt record</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {items?.length === 0 && !error && !blockedResult && !mayCreate && <p className="mt-3 text-sm text-amber-200">Saving this receipt needs a current queue item, a signed-in operator with permission, and a valid session.</p>}
    </section>;
}

function Observation({ item }: { item: QueueObservationReceiptV1 }) {
    const receipt = item.receipt_evidence;
    const observation = item.queue_observation;
    const enqueue = item.v042_enqueue;
    const expired = isExpired(item.valid_until);
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{expired ? "Queue receipt record has expired" : "Queue receipt record is current"}</p>
        <p className="mt-1">This record confirms receipt information only. It did not consume or process work.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(item.recorded_at)}; valid until {formatUtcTimestamp(item.valid_until)}. An expired record cannot be renewed.</p>
        <ol aria-label="What needs attention" className="mt-2 list-decimal pl-5">
            {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? "Atlas reported an issue that needs review."}</li>)}
        </ol>
        <details className="mt-3">
            <summary>Technical details</summary>
            <p className="mt-2">Record status: {item.lifecycle}; result: {item.disposition}; observation: {observation.observation_state}; receipt: {receipt.receipt_disposition}.</p>
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
            <details className="mt-3"><summary>Blocker codes</summary><ul className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}><code>{value}</code></li>)}</ul></details>
            <p className="mt-3 text-xs">Permanent observation subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · raw receipt persisted: false · raw queue identity persisted: false.</p>
            <p className="mt-2 text-xs">Receipt evidence is bounded and redacted; Mission Control shows only Core-supplied identifiers, timestamps, dispositions, blockers, and fingerprints.</p>
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
function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
