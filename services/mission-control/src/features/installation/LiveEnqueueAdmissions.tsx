import { useEffect, useState } from "react";

import { listLiveEnqueueAdmissions } from "../../api/liveEnqueueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { LiveEnqueueAdmissionV1 } from "../../types/liveEnqueueAdmission";
import { OneShotLiveEnqueues } from "./OneShotLiveEnqueues";

const BLOCKERS: Record<string, string> = {
    installation_capability_unsupported: "This type of installation is not supported.",
    evidence_not_found: "Required review information is missing.",
    ownership_mismatch: "This record belongs to a different owner.",
    permission_scope_missing: "The required permission is missing.",
    linkage_mismatch: "The linked records do not match.",
    fingerprint_mismatch: "A record integrity check did not pass.",
    evidence_stale: "The review information is out of date.",
    evidence_expired: "The review information has expired.",
    worker_intake_admission_not_active: "The worker intake record is not current.",
    queue_reservation_not_active: "The queue reservation is not current.",
    queue_item_reference_invalid: "The queue item reference is not valid.",
    worker_identity_ineligible: "The worker identity is not eligible.",
    worker_intake_reference_ineligible: "The worker intake reference is not eligible.",
    inherited_limits_mismatch: "The worker limits do not match the reviewed limits.",
    permanent_subject_reserved: "A review record already exists for this request.",
    enqueue_operation_not_defined: "Atlas has not set up a way to add work to the queue.",
    dequeue_not_defined: "Atlas has not set up a way to remove queued work.",
    worker_start_not_defined: "Atlas has not set up a way to start a worker.",
    execution_start_boundary_not_defined: "Atlas has not set up a safe way to start this installation.",
};

export function LiveEnqueueAdmissions({ candidateId, workerIntakeAdmissionId, homeAssistantBlocked }: { candidateId: string; workerIntakeAdmissionId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<LiveEnqueueAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listLiveEnqueueAdmissions(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.linkage.worker_intake_admission_id === workerIntakeAdmissionId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, workerIntakeAdmissionId, readAttempt]);

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Live enqueue admission evidence">
        <h6 className="font-semibold">Queue handoff review</h6>
        <p className="mt-2 text-sm">This review is read-only. It does not add work to the queue or start a worker.</p>
        <p className="mt-2 text-sm">Atlas cannot save this review until Core provides the required queue records.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">Home Assistant installation is unsupported and remains blocked.</p>}
        {items === null && !error && <p role="status" className="mt-3">Checking for a saved queue handoff review…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Atlas could not load the queue handoff review. Retry to check its current status.</p><p className="text-xs text-slate-400">Private system details are hidden.</p><button type="button" onClick={() => { setItems(null); setError(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No queue handoff review has been saved. Atlas cannot add work to the queue or start a worker.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Saved queue handoff reviews">{items.map((item) => <Admission key={item.admission_id} admission={item} />)}</ol>}
    </section>;
}

function Admission({ admission }: { admission: LiveEnqueueAdmissionV1 }) {
    const expired = isExpired(admission.valid_until);
    const decision = admission.admission_decision;
    const link = admission.linkage;
    const limits = admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{expired ? "Queue handoff review has expired" : "Queue handoff review is current"}</p>
        <p className="mt-1">This record has not added work to a queue or contacted a worker.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(admission.recorded_at)}; valid until {formatUtcTimestamp(admission.valid_until)}. An expired record cannot be renewed.</p>
        <ol aria-label="What needs attention" className="mt-2 list-decimal pl-5">
            {admission.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? "Atlas reported an issue that needs review."}</li>)}
        </ol>
        <details className="mt-3">
            <summary>Technical details</summary>
            <p className="mt-2">Record status: {admission.eligibility}; lifecycle: {admission.lifecycle}.</p>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Decision" value={decision.decision} />
                <Value name="Decision evaluated" value={formatUtcTimestamp(decision.evaluated_at)} />
                <Value name="Worker intake admission" value={link.worker_intake_admission_id} />
                <Value name="Queue reservation" value={link.queue_reservation_id} />
                <Value name="Queue item reference" value={link.queue_item_reference_id} />
                <Value name="Worker identity" value={link.worker_identity_id} />
            </dl>
            <details className="mt-3"><summary>Blocker codes</summary><ul className="mt-2 list-disc pl-5">{admission.blockers.map((value) => <li key={value}><code>{value}</code></li>)}</ul></details>
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
            <h6 className="mt-3 font-semibold">Sandbox and resource limits</h6>
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
        <OneShotLiveEnqueues candidateId={admission.candidate_record_id} liveEnqueueAdmissionId={admission.admission_id} />
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
