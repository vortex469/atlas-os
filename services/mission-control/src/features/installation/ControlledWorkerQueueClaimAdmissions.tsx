import { useEffect, useState } from "react";

import { listControlledWorkerQueueClaimAdmissions } from "../../api/controlledWorkerQueueClaimAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { ControlledWorkerQueueClaimAdmissionV1 } from "../../types/controlledWorkerQueueClaimAdmission";
import { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "./ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions";

const BLOCKERS: Record<string, string> = {
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

const V050_PREREQUISITES = [
    "one active same-owner v0.49 controlled worker queue claim admission",
    "exact inherited lineage, ownership, freshness, fingerprints, and limits",
    "bounded queue and item identity derived from admitted lineage only",
    "default-off queue adapter before any future effect",
    "reservation-before-effect for any future claim attempt",
    "permanent idempotency and subject no-replay across claim, lease, and acknowledgement",
    "terminal ambiguity handling",
    "bounded append-only redacted persistence",
    "secret-free lease and acknowledgement handle treatment",
    "operator-scoped API and UI isolation",
    "Agent and execution-worker zero-consumer behavior",
];

export function ControlledWorkerQueueClaimAdmissions({ candidateId, activationEvidenceId }: { candidateId: string; activationEvidenceId: string }) {
    const [items, setItems] = useState<ControlledWorkerQueueClaimAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listControlledWorkerQueueClaimAdmissions(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.worker_binding_activation_evidence.activation_evidence_id === activationEvidenceId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, activationEvidenceId]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Controlled worker queue claim admission evidence">
        <h6 className="font-semibold">Controlled worker queue claim admission</h6>
        <p className="mt-2 text-sm">Mission Control shows v0.49 admission evidence inside the existing installation workflow. It records that one exact v0.48 activation evidence record reached readiness for later controlled queue claim consideration only.</p>
        <p className="mt-1 text-sm">v0.50 prerequisite state: documentation-only prerequisite frozen; claim, lease, acknowledgement, worker-start admission, worker start, Agent invocation, and execution remain not defined.</p>
        <p className="mt-1 text-sm">No queue claim, queue lease, queue acknowledgement, worker-start admission, worker start, Agent invocation, execution, installation, deployment, rollback, retry, or resend control is available here.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading controlled worker queue claim admission evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Controlled worker queue claim admission evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no credential, endpoint, command, payload, queue detail, claim material, lease material, acknowledgement handle, worker address, store, runtime, broker, log, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No controlled worker queue claim admission evidence has been recorded. v0.50 remains documentation-only prerequisite closure; queue claim, lease, acknowledgement, worker-start admission, worker start, Agent invocation, and execution remain blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Controlled worker queue claim admissions">{items.map((item) => <ClaimAdmission key={item.admission_id} item={item} />)}</ol>}
    </section>;
}

function ClaimAdmission({ item }: { item: ControlledWorkerQueueClaimAdmissionV1 }) {
    const activationEvidence = item.worker_binding_activation_evidence;
    const preflight = activationEvidence.worker_binding_activation_preflight;
    const binding = preflight.one_shot_dequeue_worker_binding;
    const worker = binding.worker_intake_admission.worker_identity;
    const limits = binding.worker_intake_admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Recorded controlled worker queue claim admission evidence</p>
        <p className="mt-1">Readiness/start-admission state: queue-claim admission evidence recorded; queue claim: not defined; worker-start admission: not defined; blocked: yes. Queue claimed: false; queue leased: false; queue acknowledged: false; worker started: false; Agent invoked: false; execution started: false.</p>
        <p className="mt-1">v0.50 progress: prerequisite frozen, documentation-only. Queue claim, lease, acknowledgement, worker-start admission, worker start, Agent invocation, and execution are still unavailable.</p>
        <p className="mt-1">v0.51 state is shown below when Core has recorded it. It remains read-only evidence and does not create queue, lease, acknowledgement, worker-start, Agent, or execution authority.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Expiry is passive and never claims work, leases work, acknowledges work, admits worker start, contacts a worker, starts execution, or retries delivery.</p>
        <details className="mt-3">
            <summary>Advanced details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Admission ID" value={item.admission_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Eligibility" value={item.eligibility} />
                <Value name="Lifecycle" value={item.lifecycle} />
                <Value name="Admission state" value={item.admission_state} />
                <Value name="Admission fingerprint" value={item.admission_record_fingerprint.value} />
                <Value name="Subject fingerprint" value={item.subject_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint.value} />
                <Value name="v0.48 activation evidence" value={activationEvidence.activation_evidence_id} />
                <Value name="v0.48 activation evidence fingerprint" value={activationEvidence.activation_evidence_record_fingerprint.value} />
                <Value name="v0.48 activation evidence status fingerprint" value={item.worker_binding_activation_evidence_status.status_fingerprint.value} />
                <Value name="v0.47 preflight" value={preflight.preflight_id} />
                <Value name="v0.46 binding" value={binding.binding_id} />
                <Value name="v0.45 one-shot dequeue" value={binding.one_shot_controlled_dequeue.dequeue_id} />
                <Value name="v0.40 worker intake admission" value={binding.worker_intake_admission.admission_id} />
                <Value name="Binding subject fingerprint" value={item.binding_subject_fingerprint.value} />
                <Value name="Worker subject fingerprint" value={item.worker_subject_fingerprint.value} />
                <Value name="Worker identity ID" value={worker.worker_identity_id} />
                <Value name="Worker kind" value={worker.worker_kind} />
                <Value name="Worker trust domain" value={worker.trust_domain} />
                <Value name="Worker eligibility" value={worker.eligibility} />
                <Value name="Worker capability fingerprint" value={worker.capability_profile_fingerprint.value} />
                <Value name="Queue item reference fingerprint" value={item.queue_item_reference_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Blockers</h6>
            <ol aria-label="Ordered controlled worker queue claim admission blockers" className="mt-2 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
            <h6 className="mt-3 font-semibold">v0.50 prerequisite details</h6>
            <p className="mt-2 text-xs">The strongest v0.50 state is documentation-only prerequisite closure. It does not create a runtime record, route, schema, permission, queue operation, worker operation, Agent operation, execution operation, deployment operation, or release operation.</p>
            <ol aria-label="v0.50 controlled worker queue prerequisites" className="mt-2 list-decimal pl-5">
                {V050_PREREQUISITES.map((value) => <li key={value}>{value}</li>)}
            </ol>
            <dl aria-label="v0.50 fixed-false prerequisite equations" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["v0.50 prerequisite frozen equals queue claimed", "v0.50 prerequisite frozen equals queue leased", "v0.50 prerequisite frozen equals queue acknowledged", "v0.50 prerequisite frozen equals worker start admitted", "v0.50 prerequisite frozen equals worker started", "v0.50 prerequisite frozen equals Agent invoked", "v0.50 prerequisite frozen equals execution started", "Claim admission recorded equals queue claimed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
            <h6 className="mt-3 font-semibold">Inherited sandbox, resource, network, and filesystem limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privileged / escalation / host namespaces / devices" value="false" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Inherited limits fingerprint" value={item.inherited_limits_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">Permanent queue-claim admission subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · credential material present: false · endpoint material present: false · command material present: false · payload material present: false.</p>
            <dl aria-label="Controlled worker queue claim admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Queue polling allowed", "Queue claim allowed", "Queue claimed", "Queue lease allowed", "Queue leased", "Queue acknowledgement allowed", "Queue acknowledged", "Queue consume allowed", "Queue mutation allowed", "Worker activation runtime allowed", "Worker start admission allowed", "Worker start admitted", "Worker start allowed", "Worker started", "Worker invocation allowed", "Agent invocation allowed", "Execution authorization allowed", "Execution start allowed", "Execution started", "Process execution allowed", "Store contact allowed", "Runtime contact allowed", "Worker store contact allowed", "Worker runtime contact allowed", "Worker contact allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Workflow start allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Artifact publication allowed", "Tag push allowed", "Release publication allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={item.candidate_record_id} v049AdmissionId={item.admission_id} />
    </li>;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
