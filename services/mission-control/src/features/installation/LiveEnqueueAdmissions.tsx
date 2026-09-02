import { useEffect, useState } from "react";

import { listLiveEnqueueAdmissions } from "../../api/liveEnqueueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { LiveEnqueueAdmissionV1 } from "../../types/liveEnqueueAdmission";

const BLOCKERS: Record<string, string> = {
    installation_capability_unsupported: "Installation capability is unsupported",
    evidence_not_found: "Required evidence was not found",
    ownership_mismatch: "Ownership does not match",
    permission_scope_missing: "Permission scope is missing",
    linkage_mismatch: "Linkage does not match",
    fingerprint_mismatch: "Fingerprint does not match",
    evidence_stale: "Evidence is stale",
    evidence_expired: "Evidence is expired",
    worker_intake_admission_not_active: "Worker intake admission is not active",
    queue_reservation_not_active: "Queue reservation is not active",
    queue_item_reference_invalid: "Queue item reference is invalid",
    worker_identity_ineligible: "Worker identity is ineligible",
    worker_intake_reference_ineligible: "Worker intake reference is ineligible",
    inherited_limits_mismatch: "Inherited limits do not match",
    permanent_subject_reserved: "Permanent subject reservation already exists",
    enqueue_operation_not_defined: "Enqueue operation is not defined",
    dequeue_not_defined: "Dequeue is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
};

export function LiveEnqueueAdmissions({ candidateId, workerIntakeAdmissionId, homeAssistantBlocked }: { candidateId: string; workerIntakeAdmissionId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<LiveEnqueueAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listLiveEnqueueAdmissions(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.linkage.worker_intake_admission_id === workerIntakeAdmissionId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, workerIntakeAdmissionId]);

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Live enqueue admission evidence">
        <h6 className="font-semibold">Live enqueue admission</h6>
        <p className="mt-2 text-sm">Mission Control presents live enqueue admission evidence inside the worker-intake hierarchy. It records only inert admission evidence and does not enqueue, dequeue, poll, contact or start a worker, dispatch, install, or execute anything.</p>
        <p className="mt-2 text-sm">Creation is unavailable here because Core supplies no eligible server-owned live enqueue context. Mission Control does not invent queue items, edit inherited ceilings, expose payloads, render endpoints or credentials, or provide operational queue controls.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">For Home Assistant, live enqueue admission remains blocked by unsupported installation capability; it stays non-installable and non-executable.</p>}
        {items === null && !error && <p role="status" className="mt-3">Loading live enqueue admission evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Live enqueue admission evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, endpoint, worker address, queue detail, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No live enqueue admission evidence has been recorded. Enqueue, dequeue, polling, worker contact, worker start, dispatch, install, and execution remain blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Live enqueue admissions">{items.map((item) => <Admission key={item.admission_id} admission={item} />)}</ol>}
    </section>;
}

function Admission({ admission }: { admission: LiveEnqueueAdmissionV1 }) {
    const status = isExpired(admission.valid_until) ? "Expired" : "Recorded";
    const decision = admission.admission_decision;
    const link = admission.linkage;
    const limits = admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status} live enqueue admission evidence</p>
        <p className="mt-1">Status: {admission.eligibility}; lifecycle: {admission.lifecycle}; queue item constructed: false; payload constructed: false; payload serialized: false; request sent: false; queue enqueued: false.</p>
        <p className="mt-1">Recorded {admission.recorded_at}; valid until {admission.valid_until}. Freshness is at most 30 seconds and expiry is passive.</p>
        <ol aria-label="Ordered live enqueue admission blockers" className="mt-2 list-decimal pl-5">
            {admission.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
        </ol>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            <Value name="Decision" value={decision.decision} />
            <Value name="Decision evaluated" value={decision.evaluated_at} />
            <Value name="Worker intake admission" value={link.worker_intake_admission_id} />
            <Value name="Queue reservation" value={link.queue_reservation_id} />
            <Value name="Queue item reference" value={link.queue_item_reference_id} />
            <Value name="Worker identity" value={link.worker_identity_id} />
        </dl>
        <details className="mt-3">
            <summary>Advanced live enqueue evidence</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Admission ID" value={admission.admission_id} />
                <Value name="Authenticated operator" value={admission.operator_id} />
                <Value name="Record fingerprint" value={admission.record_fingerprint.value} />
                <Value name="Subject fingerprint" value={admission.subject_fingerprint.value} />
                <Value name="Request fingerprint" value={admission.request_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={admission.idempotency_key_fingerprint.value} />
                <Value name="Worker intake admission fingerprint" value={link.worker_intake_admission_fingerprint.value} />
                <Value name="Worker intake status fingerprint" value={link.worker_intake_admission_status_fingerprint.value} />
                <Value name="Queue reservation fingerprint" value={link.queue_reservation_fingerprint.value} />
                <Value name="Queue reservation status fingerprint" value={link.queue_reservation_status_fingerprint.value} />
                <Value name="Queue item fingerprint" value={link.queue_item_reference_fingerprint.value} />
                <Value name="Worker identity fingerprint" value={link.worker_identity_fingerprint.value} />
                <Value name="Worker intake reference fingerprint" value={link.worker_intake_reference_fingerprint.value} />
                <Value name="v0.20-v0.39 chain fingerprint" value={link.v020_v039_chain_fingerprint.value} />
                <Value name="Decision fingerprint" value={decision.decision_fingerprint.value} />
                <Value name="Linkage fingerprint" value={link.linkage_fingerprint.value} />
            </dl>
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
            <p className="mt-3 text-xs">Permanent live-enqueue subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · consumed: false · released: false · replaceable: false · supersedable: false · retry allowed: false · replay bypass allowed: false.</p>
            <p className="mt-2 text-xs">Audit facts are server-owned, redacted, and fingerprint-bound; Mission Control displays only record, subject, request, linkage, status, decision, and correlation fingerprints returned by Core.</p>
            <dl aria-label="Live enqueue admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Live enqueue allowed", "Enqueue operation defined", "Queue item payload defined", "Payload constructed", "Payload serialized", "Queue publish allowed", "Queue send allowed", "Dequeue allowed", "Queue polling allowed", "Queue claim allowed", "Queue ack allowed", "Worker contact allowed", "Worker authentication allowed", "Worker binding allowed", "Worker start allowed", "Execution start allowed", "Runner binding allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
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
