import { useEffect, useState } from "react";

import { listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import type { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 } from "../../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";

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
        <h6 className="font-semibold">Controlled queue claim, lease, and acknowledgement admission</h6>
        <p className="mt-2 text-sm">v0.51 state: admission evidence recorded for the completed v0.50 prerequisite. Queue adapter, claim, lease, acknowledgement, worker-start admission, worker start, Agent invocation, and execution remain not defined.</p>
        <p className="mt-1 text-sm">Mission Control reads this state from Core and presents it inside the existing installation workflow. No queue, worker, Agent, installation, deployment, rollback, retry, resend, or workflow control is available here.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading controlled queue claim lease acknowledgement admission evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Controlled queue claim lease acknowledgement admission evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no credential, endpoint, command, payload, queue selector, claim token, lease token, acknowledgement handle, worker address, store, runtime, broker, log, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No controlled queue claim lease acknowledgement admission evidence has been recorded for this claim admission. Queue claim, lease, acknowledgement, worker-start admission, worker start, Agent invocation, and execution remain blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Controlled queue claim lease acknowledgement admissions">{items.map((item) => <Admission key={item.admission_id} item={item} />)}</ol>}
    </section>;
}

function Admission({ item }: { item: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 }) {
    const prerequisite = item.controlled_worker_queue_claim_lease_acknowledgement_prerequisite;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Recorded v0.51 admission evidence</p>
        <p className="mt-1">Operator state: claim/lease/ack admission evidence recorded; queue adapter: not defined; queue claim: not defined; queue lease: not defined; queue acknowledgement: not defined; worker-start admission: not defined; blocked: yes.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Expiry is passive and never claims work, leases work, acknowledges work, admits worker start, contacts a worker, starts execution, or retries delivery.</p>
        <details className="mt-3">
            <summary>Advanced v0.51 evidence</summary>
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
    </li>;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string | FingerprintV1 }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
