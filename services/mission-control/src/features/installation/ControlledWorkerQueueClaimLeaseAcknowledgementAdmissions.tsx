import { useEffect, useState } from "react";

import { listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import type { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 } from "../../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import { ControlledWorkerQueueReceipt } from "./ControlledWorkerQueueReceipt";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

export function ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions({ candidateId, v049AdmissionId }: { candidateId: string; v049AdmissionId: string }) {
    return <AdmissionReader key={`${candidateId}:${v049AdmissionId}`} candidateId={candidateId} v049AdmissionId={v049AdmissionId} />;
}

function AdmissionReader({ candidateId, v049AdmissionId }: { candidateId: string; v049AdmissionId: string }) {
    const [items, setItems] = useState<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions(candidateId)
            .then((value) => {
                if (current) setItems(value.items.filter((item) => item.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.admission_id === v049AdmissionId));
            })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, v049AdmissionId]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Controlled worker queue claim lease acknowledgement admission evidence">
        <h6 className="font-semibold">Queue operation readiness</h6>
        <p className="mt-2 text-sm">This is a read-only record from Core. It does not claim, lease, or acknowledge queue work, or start a worker.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading queue readiness...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Queue readiness is unavailable.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No queue readiness record is available for this claim. Queue operations and worker start remain unavailable.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Controlled queue claim lease acknowledgement admissions">{items.map((item) => <Admission key={item.admission_id} item={item} />)}</ol>}
    </section>;
}

function Admission({ item }: { item: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 }) {
    const prerequisite = item.controlled_worker_queue_claim_lease_acknowledgement_prerequisite;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Queue readiness recorded</p>
        <BlockerSummary blockers={item.blockers} />
        <p className="mt-2">This record only lists requirements. It cannot operate the queue or start a worker.</p>
        <p className="mt-1">Core may also show the queue receipt below. It reports recorded queue state and does not add actions here.</p>
        <p className="mt-1">Recorded {formatDateTime(item.recorded_at)} · Expires {formatDateTime(item.valid_until)}. Expiry does not trigger an action.</p>
        <details className="mt-3">
            <summary>Advanced details</summary>
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
                {item.blockers.map((value) => <li key={value}>{workerBindingActivationBlockerLabel(value)} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
            <dl aria-label="Controlled queue claim lease acknowledgement fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Queue adapter defined", "Queue polling allowed", "Queue claim allowed", "Queue claimed", "Queue lease allowed", "Queue leased", "Queue acknowledgement allowed", "Queue acknowledged", "Queue requeue allowed", "Queue mutation allowed", "Worker activation runtime allowed", "Worker start admission allowed", "Worker start admitted", "Worker start allowed", "Worker started", "Agent invocation allowed", "Agent invoked", "Execution start allowed", "Execution started", "Store contact allowed", "Runtime contact allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Workflow start allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Artifact publication allowed", "Tag push allowed", "Release publication allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
            <p className="mt-3 text-xs">Core-owned evidence only. Mission Control displays identifiers and fingerprints returned by Core; raw queue selectors, claim tokens, lease tokens, acknowledgement handles, payloads, commands, endpoints, and credentials are not accepted or shown.</p>
        </details>
        <ControlledWorkerQueueReceipt candidateId={item.candidate_record_id} admissionId={item.admission_id} operatorId={item.operator_id} />
    </li>;
}

function BlockerSummary({ blockers }: { blockers: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-1">No blockers are listed. This record still does not operate the queue.</p>;
    return <div className="mt-1 rounded border border-amber-500/40 p-2" aria-label="Queue operation status">
        <p className="font-semibold">Queue operations are blocked</p>
        <p>{blockers.length} {blockers.length === 1 ? "requirement remains" : "requirements remain"} unavailable.</p>
        <details className="mt-1">
            <summary>Show what needs to be in place</summary>
            <ul aria-label="Queue operation blockers" className="mt-2 list-disc pl-5">
                {blockers.map((blocker) => <li key={blocker}>{workerBindingActivationBlockerLabel(blocker)}</li>)}
            </ul>
        </details>
    </div>;
}

function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string | FingerprintV1 }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
