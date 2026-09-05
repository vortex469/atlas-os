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
    installation_capability_unsupported: "Installation capability unsupported",
    evidence_not_found: "Evidence not found",
    ownership_mismatch: "Ownership mismatch",
    permission_scope_missing: "Permission scope missing",
    linkage_mismatch: "Linkage mismatch",
    fingerprint_mismatch: "Fingerprint mismatch",
    evidence_stale: "Evidence stale",
    evidence_expired: "Evidence expired",
    v042_enqueue_not_active: "v0.42 enqueue is not active",
    v042_enqueue_not_recorded: "v0.42 enqueue is not recorded",
    queue_identity_mismatch: "Queue identity mismatch",
    item_identity_mismatch: "Item identity mismatch",
    receipt_evidence_invalid: "Receipt evidence invalid",
    observation_malformed: "Observation malformed",
    ambiguous_state: "Ambiguous state",
    executable_payload: "Executable payload",
    unsupported_authority: "Unsupported authority",
    dequeue_not_defined: "Dequeue is not defined",
    queue_polling_not_defined: "Queue polling is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
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
    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Queue observation and enqueue receipt evidence">
        <h6 className="font-semibold">Queue observation and enqueue receipt</h6>
        <p className="mt-2 text-sm">State: {observed ? "Observed" : "Pending or blocked"}. The v0.42 inert item remains queued evidence only; this panel does not consume or process it.</p>
        <p className="mt-1 text-sm">This is not dequeue, polling as a consumer, claim, lease, acknowledgement, worker contact, worker start, Agent invocation, workflow start, dispatch, retry, resend, installation, deployment, rollback, mutation, or execution.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading queue observation evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Queue observation evidence is unavailable or blocked.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, endpoint, worker address, queue detail, broker, raw receipt, or internal path is shown.</p></div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>Queue observation remains pending or blocked.</p><p className="mt-1 text-xs">Disposition: {blockedResult.outcome}; blocker: {BLOCKERS[blockedResult.error.error_code] ?? blockedResult.error.error_code}. Retry, resend, dequeue, worker start, and execution remain unavailable.</p></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No observation receipt evidence has been recorded for this queued item.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Queue observation receipts">{items.map((item) => <Observation key={item.receipt_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review queue observation evidence statement</button>}
        {mayCreate && confirming && <div aria-label="Queue observation evidence confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Step 2 of 2 - explicitly record observation evidence</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core binds the authenticated operator, exact v0.42 enqueue, exact inert queue item, inherited ceilings, receipt evidence, and permanent no-replay reservation.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Record observation evidence</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-3 text-sm text-amber-200">Recording remains blocked. An active v0.42 enqueue, authenticated owner, dedicated queue observation permission, and valid CSRF session are required.</p>}
    </section>;
}

function Observation({ item }: { item: QueueObservationReceiptV1 }) {
    const receipt = item.receipt_evidence;
    const observation = item.queue_observation;
    const enqueue = item.v042_enqueue;
    const status = isExpired(item.valid_until) ? "Expired observed evidence" : "Observed queued item";
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status}</p>
        <p className="mt-1">Lifecycle: {item.lifecycle}; disposition: {item.disposition}; observation state: {observation.observation_state}; receipt disposition: {receipt.receipt_disposition}.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Expiry is passive and does not refresh, dequeue, retry, resend, or start work.</p>
        <details className="mt-3">
            <summary>Advanced queue observation details</summary>
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
            <ol aria-label="Ordered queue observation blockers" className="mt-3 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
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
