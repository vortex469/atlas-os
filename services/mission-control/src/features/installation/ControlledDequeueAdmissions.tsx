import { useEffect, useState } from "react";

import { createControlledDequeueAdmission, controlledDequeueAdmissionCreateFromObservation, controlledDequeueAdmissionIdempotencyKey, listControlledDequeueAdmissions } from "../../api/controlledDequeueAdmission";
import { getQueueObservation } from "../../api/queueObservation";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ControlledDequeueAdmissionResultV1, ControlledDequeueAdmissionV1 } from "../../types/controlledDequeueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { QueueObservationReceiptV1 } from "../../types/queueObservation";

const CONFIRMATION = "Record controlled dequeue admission evidence only. This does not dequeue, poll, claim, lease, acknowledge, consume, remove, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything.";

const BLOCKERS: Record<string, string> = {
    installation_capability_unsupported: "Installation capability unsupported",
    evidence_not_found: "Evidence not found",
    ownership_mismatch: "Ownership mismatch",
    permission_scope_missing: "Permission scope missing",
    v043_observation_not_active: "v0.43 observation is not active",
    v043_observation_not_recorded: "v0.43 observation is not recorded",
    v043_receipt_not_contract_eligible: "v0.43 receipt is not contract eligible",
    v042_enqueue_not_active: "v0.42 enqueue is not active",
    v042_enqueue_not_recorded: "v0.42 enqueue is not recorded",
    linkage_mismatch: "Linkage mismatch",
    queue_identity_mismatch: "Queue identity mismatch",
    item_identity_mismatch: "Item identity mismatch",
    observation_receipt_mismatch: "Observation receipt mismatch",
    fingerprint_mismatch: "Fingerprint mismatch",
    inherited_limits_mismatch: "Inherited limits mismatch",
    evidence_stale: "Evidence stale",
    evidence_expired: "Evidence expired",
    ambiguous_state: "Ambiguous state",
    executable_payload: "Executable payload",
    unsupported_authority: "Unsupported authority",
    permanent_subject_reserved: "Permanent subject already reserved",
    idempotency_conflict: "Idempotency conflict",
    append_indeterminate: "Append indeterminate",
    dequeue_not_defined: "Dequeue is not defined",
    queue_polling_not_defined: "Queue polling is not defined",
    queue_claim_not_defined: "Queue claim is not defined",
    queue_lease_not_defined: "Queue lease is not defined",
    queue_ack_not_defined: "Queue acknowledgement is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
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
    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Controlled dequeue admission evidence">
        <h6 className="font-semibold">Controlled dequeue admission</h6>
        <p className="mt-2 text-sm">Readiness: {admitted ? "Ready for later dequeue consideration" : "Blocked or not yet admitted"}. This is evidence for a future boundary only.</p>
        <p className="mt-1 text-sm">No dequeue, queue polling, claim, lease, acknowledgement, consume, remove, worker start, Agent invocation, execution, installation, deployment, rollback, retry, or resend control is available here.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading controlled dequeue admission evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Controlled dequeue admission evidence is unavailable or blocked.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, endpoint, worker address, queue detail, broker, queue-control secret, or internal path is shown.</p></div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>Controlled dequeue admission remains blocked.</p><p className="mt-1 text-xs">Disposition: {blockedResult.outcome}; blocker: {BLOCKERS[blockedResult.error.error_code] ?? blockedResult.error.error_code}. Dequeue and worker execution remain unavailable.</p></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No controlled dequeue admission evidence has been recorded for this queue observation.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Controlled dequeue admissions">{items.map((item) => <Admission key={item.admission_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review controlled dequeue admission statement</button>}
        {mayCreate && confirming && <div aria-label="Controlled dequeue admission confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Step 2 of 2 - explicitly record controlled dequeue admission evidence</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core binds the authenticated operator, exact v0.43 observation receipt and status, exact inert v0.42 queue item, inherited limits, freshness, and permanent no-replay reservations.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Record admission evidence</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-3 text-sm text-amber-200">Recording remains blocked. An active v0.43 observation, authenticated owner, dedicated controlled dequeue admission permissions, queue observation read permission, and valid CSRF session are required.</p>}
    </section>;
}

function Admission({ item }: { item: ControlledDequeueAdmissionV1 }) {
    const status = isExpired(item.valid_until) ? "Expired readiness evidence" : "Ready for later dequeue consideration";
    const receipt = item.queue_observation_receipt;
    const queueItem = receipt.v042_enqueue.queue_item;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status}</p>
        <p className="mt-1">Admission state: {item.admission_state}; eligibility: {item.eligibility}; disposition: {item.disposition}.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Freshness is passive and does not dequeue, poll, claim, lease, acknowledge, consume, remove, retry, resend, or start work.</p>
        <details className="mt-3">
            <summary>Advanced controlled dequeue admission details</summary>
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
            <ol aria-label="Ordered controlled dequeue admission blockers" className="mt-3 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
            <p className="mt-3 text-xs">Audit events are bounded to controlled_dequeue_admission_recorded, controlled_dequeue_admission_read, and controlled_dequeue_admission_indeterminate. Permanent subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false.</p>
            <p className="mt-2 text-xs">Mission Control shows only Core-supplied lineage, identifiers, fingerprints, ownership, freshness, blockers, admission status, and audit details; raw queue, broker, lease, acknowledgement, worker, command, and payload details are not displayed.</p>
            <dl aria-label="Controlled dequeue admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Payload schema defined", "Payload constructed", "Payload serialized", "Executable payload allowed", "Dequeue defined", "Dequeue allowed", "Dequeue attempted", "Dequeued", "Queue polling allowed", "Queue polled", "Queue claim allowed", "Queue claimed", "Queue lease allowed", "Queue leased", "Queue ack allowed", "Queue acked", "Queue consumed", "Worker contact allowed", "Worker contacted", "Worker start allowed", "Worker started", "Agent invocation allowed", "Execution start allowed", "Process execution allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Scheduler allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Container execution allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
