import { useEffect, useState } from "react";

import { listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import type { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 } from "../../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";

import { ControlledWorkerQueueReceipt } from "./ControlledWorkerQueueReceipt";

const BLOCKERS: Record<string, string> = {
    queue_adapter_not_defined: "Queue adapter is not defined",
    queue_claim_not_defined: "Queue claim is not defined",
    queue_lease_not_defined: "Queue lease is not defined",
    queue_ack_not_defined: "Queue acknowledgement is not defined",
    worker_activation_runtime_not_defined: "Worker activation runtime is not defined",
    store_contact_not_defined: "Store contact is not defined",
    runtime_contact_not_defined: "Runtime contact is not defined",
    worker_start_admission_not_defined: "Worker start admission is not defined",
    worker_start_not_defined: "Worker start is not defined",
    agent_invocation_not_defined: "Agent invocation is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
};

export function ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions({ candidateId, v049AdmissionId }: { candidateId: string; v049AdmissionId: string }) {
    return <AdmissionReader key={`${candidateId}:${v049AdmissionId}`} candidateId={candidateId} v049AdmissionId={v049AdmissionId} />;
}

function AdmissionReader({ candidateId, v049AdmissionId }: { candidateId: string; v049AdmissionId: string }) {
    const [items, setItems] = useState<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions(candidateId)
            .then((value) => {
                if (current) {
                    setItems(value.items.filter((item) => item.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.admission_id === v049AdmissionId));
                    setError(false);
                }
            })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, v049AdmissionId, readAttempt]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Queue and worker review status">
        <h6 className="font-semibold">Queue and worker review</h6>
        <p className="mt-2 text-sm">This saved review checks the required queue and worker details. It does not claim queue work or start a worker.</p>
        {items === null && !error && <p role="status" className="mt-3">Checking the saved review…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Atlas could not load the saved review. Retry to check its status.</p><p className="text-xs text-slate-400">Private system details are hidden.</p><button type="button" onClick={() => { setItems(null); setError(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No review has been saved. Queue access and worker start are unavailable.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Controlled queue claim lease acknowledgement admissions">{items.map((item) => <Admission key={item.admission_id} item={item} />)}</ol>}
    </section>;
}

function Admission({ item }: { item: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 }) {
    const prerequisite = item.controlled_worker_queue_claim_lease_acknowledgement_prerequisite;
    const status = isExpired(item.valid_until) ? "Expired" : "Saved";
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Queue and worker review {status.toLowerCase()}</p>
        <p className="mt-1">Queue access and worker start are not available. This record only saves review evidence.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(item.recorded_at)} · Expires {formatUtcTimestamp(item.valid_until)}</p>
        <details className="mt-3">
            <summary>Technical details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="v0.51 admission ID" value={item.admission_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Candidate record ID" value={item.candidate_record_id} />
                <Value name="Admission state" value={item.admission_state} />
                <Value name="Eligibility" value={item.eligibility} />
                <Value name="v0.51 admission fingerprint" value={item.admission_record_fingerprint} />
                <Value name="v0.51 subject fingerprint" value={item.subject_fingerprint} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint} />
                <Value name="v0.50 prerequisite ID" value={item.prerequisite_id} />
                <Value name="v0.50 prerequisite state" value={prerequisite.prerequisite_state} />
                <Value name="v0.50 prerequisite eligibility" value={prerequisite.eligibility} />
                <Value name="v0.50 prerequisite record fingerprint" value={item.prerequisite_record_fingerprint} />
                <Value name="v0.50 prerequisite status fingerprint" value={item.prerequisite_status_fingerprint} />
                <Value name="v0.49 admission record fingerprint" value={item.v049_admission_record_fingerprint} />
                <Value name="v0.49 admission status fingerprint" value={item.v049_admission_status_fingerprint} />
                <Value name="Binding subject fingerprint" value={item.binding_subject_fingerprint} />
                <Value name="Worker subject fingerprint" value={item.worker_subject_fingerprint} />
                <Value name="Queue item reference fingerprint" value={item.queue_item_reference_fingerprint} />
                <Value name="Inherited limits fingerprint" value={item.inherited_limits_fingerprint} />
            </dl>
            <h6 className="mt-3 font-semibold">Ordered v0.51 blockers</h6>
            <ol aria-label="Ordered controlled queue claim lease acknowledgement admission blockers" className="mt-2 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
            <dl aria-label="Controlled queue claim lease acknowledgement fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Queue adapter defined", "Queue polling allowed", "Queue claim allowed", "Queue claimed", "Queue lease allowed", "Queue leased", "Queue acknowledgement allowed", "Queue acknowledged", "Queue requeue allowed", "Queue mutation allowed", "Worker activation runtime allowed", "Worker start admission allowed", "Worker start admitted", "Worker start allowed", "Worker started", "Agent invocation allowed", "Agent invoked", "Execution start allowed", "Execution started", "Store contact allowed", "Runtime contact allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Workflow start allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Artifact publication allowed", "Tag push allowed", "Release publication allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
            <p className="mt-3 text-xs">Core-owned evidence only. Mission Control displays identifiers and fingerprints returned by Core; raw queue selectors, claim tokens, lease tokens, acknowledgement handles, payloads, commands, endpoints, and credentials are not accepted or shown.</p>
        </details>
        <ControlledWorkerQueueReceipt candidateId={item.candidate_record_id} admissionId={item.admission_id} operatorId={item.operator_id} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string | FingerprintV1 }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
