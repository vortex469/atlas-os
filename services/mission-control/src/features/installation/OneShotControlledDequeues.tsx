import { useEffect, useState } from "react";

import { getControlledDequeueAdmission } from "../../api/controlledDequeueAdmission";
import { createOneShotControlledDequeue, listOneShotControlledDequeues, oneShotControlledDequeueCreateFromAdmission, oneShotControlledDequeueIdempotencyKey } from "../../api/oneShotControlledDequeue";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ControlledDequeueAdmissionV1 } from "../../types/controlledDequeueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotControlledDequeueResultV1, OneShotControlledDequeueV1 } from "../../types/oneShotControlledDequeue";
import { OneShotDequeueWorkerBindings } from "./OneShotDequeueWorkerBindings";

const CONFIRMATION = "Record one-shot controlled dequeue receipt for the exact admitted inert item only. This does not poll, claim, lease, acknowledge, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything else.";

const BLOCKERS: Record<string, string> = {
    installation_capability_unsupported: "Installation capability unsupported",
    evidence_not_found: "Evidence not found",
    ownership_mismatch: "Ownership mismatch",
    permission_scope_missing: "Permission scope missing",
    v044_admission_not_active: "v0.44 admission is not active",
    v044_admission_not_recorded: "v0.44 admission is not recorded",
    v044_admission_not_eligible: "v0.44 admission is not eligible",
    v043_observation_not_active: "v0.43 observation is not active",
    v043_observation_not_recorded: "v0.43 observation is not recorded",
    v043_receipt_not_contract_eligible: "v0.43 receipt is not contract eligible",
    v042_enqueue_not_active: "v0.42 enqueue is not active",
    v042_enqueue_not_recorded: "v0.42 enqueue is not recorded",
    linkage_mismatch: "Lineage mismatch",
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
    dequeue_adapter_unavailable: "Dequeue adapter unavailable",
    dequeue_receipt_mismatch: "Dequeue receipt mismatch",
    reservation_before_effect_failed: "Reservation before effect failed",
    permanent_subject_reserved: "Permanent subject already reserved",
    idempotency_conflict: "Idempotency conflict",
    append_indeterminate: "Append indeterminate",
    dequeue_indeterminate: "Dequeue completion indeterminate",
    queue_polling_not_defined: "Queue polling is not defined",
    queue_claim_not_defined: "Queue claim is not defined",
    queue_lease_not_defined: "Queue lease is not defined",
    queue_ack_not_defined: "Queue acknowledgement is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
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
    const state = latest
        ? latest.disposition === "exact_inert_item_dequeued"
            ? "Exact inert item dequeued"
            : latest.disposition === "exact_inert_item_not_dequeued"
              ? "Exact inert item not dequeued"
              : "Completion indeterminate"
        : "Pending or blocked";

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="One-shot controlled dequeue evidence">
        <h6 className="font-semibold">One-shot controlled dequeue</h6>
        <p className="mt-2 text-sm">State: {state}. This panel is limited to the exact admitted inert item receipt frozen by Core.</p>
        <p className="mt-1 text-sm">No polling, claim, lease, acknowledgement, worker contact, worker start, Agent invocation, execution, installation, deployment, rollback, retry, or resend control is available here.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading one-shot controlled dequeue evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>One-shot controlled dequeue evidence is unavailable or blocked.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, endpoint, worker address, queue detail, broker, lease credential, acknowledgement credential, or internal path is shown.</p></div>}
        {blockedResult?.error && <div role="alert" className="mt-3 rounded border border-amber-400/40 p-3"><p>One-shot controlled dequeue remains blocked.</p><p className="mt-1 text-xs">Disposition: {blockedResult.outcome}; blocker: {BLOCKERS[blockedResult.error.error_code] ?? blockedResult.error.error_code}. Worker execution, retry, resend, installation, and deployment remain unavailable.</p></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No one-shot controlled dequeue receipt has been recorded for this admission.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="One-shot controlled dequeue receipts">{items.map((item) => <Receipt key={item.dequeue_id} item={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-3 rounded border border-blue-400 px-3 py-2 text-sm">Review one-shot controlled dequeue statement</button>}
        {mayCreate && confirming && <div aria-label="One-shot controlled dequeue confirmation" className="mt-3 rounded border border-amber-400/40 p-3">
            <p className="font-semibold">Step 2 of 2 - explicitly record one-shot controlled dequeue receipt</p>
            <p className="mt-2 text-sm">{CONFIRMATION}</p>
            <p className="mt-2 text-xs">Core binds the authenticated operator, exact v0.44 admission, exact v0.43 observation receipt, exact inert v0.42 item, inherited limits, and permanent no-replay reservations.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Record exact inert item receipt</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-3 text-sm text-amber-200">Recording remains blocked. An active v0.44 admission, authenticated owner, dedicated one-shot controlled dequeue permissions, controlled dequeue admission read permission, and valid CSRF session are required.</p>}
    </section>;
}

function Receipt({ item }: { item: OneShotControlledDequeueV1 }) {
    const status = isExpired(item.valid_until) ? "Expired receipt evidence" : "Recorded receipt evidence";
    const admission = item.controlled_dequeue_admission;
    const observation = admission.queue_observation_receipt;
    const enqueue = observation.v042_enqueue;
    const bounded = item.bounded_receipt;
    const limits = item.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status}</p>
        <p className="mt-1">Receipt state: {item.dequeue_state}; disposition: {item.disposition}; exact admitted item only: true; adapter receipt redacted: true.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Expiry is passive and does not retry, resend, start work, or execute anything.</p>
        <details className="mt-3">
            <summary>Advanced one-shot controlled dequeue details</summary>
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
            </dl>
            <ol aria-label="Ordered one-shot controlled dequeue blockers" className="mt-3 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
            <h6 className="mt-3 font-semibold">Inherited sandbox, resource, network, and filesystem ceilings</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privileged / escalation / host namespaces / devices" value="false" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Inherited limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">Permanent dequeue subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · raw adapter receipt persisted: false · replay bypass allowed: false.</p>
            <p className="mt-2 text-xs">Mission Control shows only Core-supplied state, lineage, queue and item identity, reservation evidence, bounded receipt facts, blockers, and fingerprints; raw queue, broker, lease, acknowledgement, worker, command, and payload details are not displayed.</p>
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
