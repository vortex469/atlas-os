import { useEffect, useState } from "react";

import { listWorkerIntakeAdmissions } from "../../api/workerIntakeAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { WorkerIntakeAdmissionV1 } from "../../types/workerIntakeAdmission";
import { LiveEnqueueAdmissions } from "./LiveEnqueueAdmissions";

const BLOCKERS: Record<string, string> = {
    live_enqueue_not_defined: "Live enqueue is not defined",
    dequeue_not_defined: "Dequeue is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
};

export function WorkerIntakeAdmissions({ candidateId, reservationId, homeAssistantBlocked }: { candidateId: string; reservationId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<WorkerIntakeAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listWorkerIntakeAdmissions(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.linkage.queue_reservation_id === reservationId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, reservationId]);

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Worker intake admission evidence">
        <h6 className="font-semibold">Worker intake admission</h6>
        <p className="mt-2 text-sm">Mission Control shows the worker intake admission status here in the existing worker flow. It is evidence only and does not send work to a queue or start a worker.</p>
        <p className="mt-2 text-sm">No execution controls are available here. This is not live enqueue, dequeue, worker contact, worker start, dispatch, execution, Agent invocation, workflow start, provider mutation, repository mutation, in-guest mutation, installation, deployment, rollback, retry, resend, or permission to mutate anything.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">For Home Assistant, worker intake admission remains blocked; it stays non-installable and non-executable.</p>}
        {items === null && !error && <p role="status" className="mt-3">Loading worker intake admission status…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Worker intake admission status is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, endpoint, worker address, queue detail, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No worker intake admission evidence has been recorded. Queue handoff, worker start, and execution remain blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Worker intake admissions">{items.map((item) => <Admission key={item.admission_id} admission={item} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Admission({ admission, homeAssistantBlocked }: { admission: WorkerIntakeAdmissionV1; homeAssistantBlocked: boolean }) {
    const status = isExpired(admission.valid_until) ? "Expired" : "Recorded";
    const identity = admission.worker_identity;
    const intake = admission.worker_intake_reference;
    const decision = admission.admission_decision;
    const limits = admission.inherited_limits;
    const link = admission.linkage;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status} worker intake admission evidence</p>
        <p className="mt-1">Status: {admission.eligibility}; lifecycle: {admission.lifecycle}; intake protocol: {intake.intake_protocol}; worker contacted: false; worker started: false; work enqueued: false.</p>
        <p className="mt-1">Recorded {admission.recorded_at}; valid until {admission.valid_until}. Freshness is at most 30 seconds and expiry is passive.</p>
        <ol aria-label="Ordered worker intake admission blockers" className="mt-2 list-decimal pl-5">
            {admission.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
        </ol>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            <Value name="Worker identity" value={identity.worker_identity_id} />
            <Value name="Worker eligibility" value={identity.eligibility} />
            <Value name="Intake reference" value={intake.worker_intake_reference_id} />
            <Value name="Intake eligibility" value={intake.eligibility} />
            <Value name="Decision" value={decision.decision} />
            <Value name="Decision evaluated" value={decision.evaluated_at} />
        </dl>
        <details className="mt-3">
            <summary>Advanced details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Admission ID" value={admission.admission_id} />
                <Value name="Authenticated operator" value={admission.operator_id} />
                <Value name="Record fingerprint" value={admission.record_fingerprint.value} />
                <Value name="Subject fingerprint" value={admission.subject_fingerprint.value} />
                <Value name="Request fingerprint" value={admission.request_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={admission.idempotency_key_fingerprint.value} />
                <Value name="Worker identity fingerprint" value={identity.worker_identity_fingerprint.value} />
                <Value name="Worker capability fingerprint" value={identity.capability_profile_fingerprint.value} />
                <Value name="Worker intake fingerprint" value={intake.intake_reference_fingerprint.value} />
                <Value name="Decision fingerprint" value={decision.decision_fingerprint.value} />
                <Value name="v0.20-v0.38 chain fingerprint" value={link.v020_v038_chain_fingerprint.value} />
                <Value name="Queue reservation fingerprint" value={link.queue_reservation_fingerprint.value} />
                <Value name="Queue reservation status fingerprint" value={link.queue_reservation_status_fingerprint.value} />
                <Value name="Worker admission stub fingerprint" value={link.worker_admission_stub_fingerprint.value} />
                <Value name="Runner binding plan fingerprint" value={link.runner_binding_plan_fingerprint.value} />
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
            <p className="mt-3 text-xs">Permanent worker-intake subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · retry allowed: false · replay bypass allowed: false.</p>
            <dl aria-label="Worker intake admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Live enqueue allowed", "Dequeue allowed", "Queue polling allowed", "Worker contact allowed", "Worker start allowed", "Execution start allowed", "Runner binding allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <LiveEnqueueAdmissions candidateId={admission.candidate_record_id} workerIntakeAdmissionId={admission.admission_id} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
