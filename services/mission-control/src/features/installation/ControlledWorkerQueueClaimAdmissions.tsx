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
    const [readAttempt, setReadAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listControlledWorkerQueueClaimAdmissions(candidateId)
            .then((value) => { if (current) { setItems(value.items.filter((item) => item.worker_binding_activation_evidence.activation_evidence_id === activationEvidenceId)); setError(false); } })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, activationEvidenceId, readAttempt]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Controlled worker queue claim admission evidence">
        <h6 className="font-semibold">Queue access review</h6>
        <p className="mt-2 text-sm">This record links the approved worker and queue references. It does not claim work or start a worker.</p>
        {items === null && !error && <p role="status" className="mt-3">Checking the queue review…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Atlas could not load the queue review. Retry to check its status.</p><p className="text-xs text-slate-400">Private system details are hidden.</p><button type="button" onClick={() => { setItems(null); setError(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No queue review has been saved. Queue access remains unavailable.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Controlled worker queue claim admissions">{items.map((item) => <ClaimAdmission key={item.admission_id} item={item} />)}</ol>}
    </section>;
}

function ClaimAdmission({ item }: { item: ControlledWorkerQueueClaimAdmissionV1 }) {
    const activationEvidence = item.worker_binding_activation_evidence;
    const preflight = activationEvidence.worker_binding_activation_preflight;
    const binding = preflight.one_shot_dequeue_worker_binding;
    const worker = binding.worker_intake_admission.worker_identity;
    const limits = binding.worker_intake_admission.inherited_limits;
    const status = isExpired(item.valid_until) ? "Expired" : "Saved";
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Queue review {status.toLowerCase()}</p>
        <p className="mt-1">Queue access is unavailable. No work was claimed, and no worker was started.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(item.recorded_at)} · Expires {formatUtcTimestamp(item.valid_until)}</p>
        <details className="mt-3">
            <summary>Technical details</summary>
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

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
