import { useEffect, useState } from "react";

import { listWorkerAdmissionStubs } from "../../api/workerAdmissionStub";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { RunnerBindingPlanResultV1 } from "../../types/runnerBindingPlan";
import type { WorkerAdmissionStubResultV1 } from "../../types/workerAdmissionStub";
import { WorkerQueueReservations } from "./WorkerQueueReservations";

const BLOCKERS: Record<string, string> = {
    worker_not_started: "Worker is not started",
    queue_boundary_not_defined: "Queue boundary is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
};

export function WorkerAdmissionStubs({ candidateId, bindingPlan, homeAssistantBlocked }: { candidateId: string; bindingPlan: RunnerBindingPlanResultV1; homeAssistantBlocked: boolean }) {
    const [stubs, setStubs] = useState<WorkerAdmissionStubResultV1[] | null>(null);
    const [error, setError] = useState(false);
    useEffect(() => {
        let current = true;
        listWorkerAdmissionStubs(candidateId)
            .then((value) => { if (current) setStubs(value.stubs.filter((item) => item.stub?.linkage.runner_binding_plan_id === bindingPlan.plan?.plan_id)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, bindingPlan.plan?.plan_id]);

    return <section aria-labelledby={`worker-admission-stubs-${bindingPlan.plan?.plan_id}`} className="mt-4 rounded border border-slate-700 p-4">
        <h5 id={`worker-admission-stubs-${bindingPlan.plan?.plan_id}`} className="font-semibold">Worker admission stub evidence</h5>
        <p className="mt-2 text-sm">This preserves a non-enqueuing worker admission stub evidence record only. A worker_admission_stubbed state is evidence, not effect or mutation authority.</p>
        <p className="mt-2 text-sm">This is not worker start, queue or enqueue, execution start, runner binding, install, dispatch, retry or resend, Agent invocation, workflow start, Docker, Podman, shell or process execution, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or permission to mutate anything.</p>
        <p className="mt-2 text-sm">Creation is unavailable here because Core exposes no eligible worker reference to Mission Control. Mission Control does not discover or contact workers, invent references or intake data, or edit inherited ceilings. The guarded v0.38 create API is the only permitted stub-evidence mutation.</p>
        {homeAssistantBlocked && <p className="mt-3 text-sm text-amber-200">For Home Assistant, worker admission remains blocked; it stays non-installable and non-executable.</p>}
        {stubs === null && !error && <p role="status" className="mt-4">Loading worker admission stub evidence…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>Worker admission stub evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no provider payload, credential, command, log, endpoint, address, queue, worker address, mount source, or internal path is shown.</p></div>}
        {stubs?.length === 0 && <p role="status" className="mt-4">No worker admission stub evidence has been recorded. Worker start, queueing, and execution remain blocked.</p>}
        {stubs && stubs.length > 0 && <ol aria-label="Worker admission stubs" className="mt-4 space-y-4">{stubs.map((item) => <Stub key={item.stub!.stub_id} result={item} candidateId={candidateId} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Stub({ result, candidateId, homeAssistantBlocked }: { result: WorkerAdmissionStubResultV1; candidateId: string; homeAssistantBlocked: boolean }) {
    const stub = result.stub!; const status = result.status!; const audit = result.audit_evidence!;
    const worker = stub.worker_reference; const intent = stub.worker_admission_intent; const intake = stub.worker_admission_intake; const limits = stub.inherited_limits; const linkage = stub.linkage;
    const lifecycle = status.lifecycle === "active" ? "Active" : "Expired";
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{lifecycle} worker admission evidence</h6>
        <p className="mt-1">State: eligible evidence; bound: false; blocked: yes. Worker contacted: false; worker started: false; work enqueued: false.</p>
        <p className="mt-1">Recorded {stub.recorded_at}; valid until {stub.valid_until}; observed {status.observed_at}. Freshness is inherited for at most 30 seconds and expiry is passive.</p>
        <details className="mt-3">
            <summary>Advanced details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Eligibility" value={stub.eligibility} /><Value name="Lifecycle" value={status.lifecycle} /><Value name="Disposition" value={result.disposition} /><Value name="Record state" value={stub.record_state} />
                <Value name="Authenticated operator" value={stub.operator_id} /><Value name="Stub ID" value={stub.stub_id} /><Value name="Stub fingerprint" value={stub.stub_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} />
                <Value name="Worker reference ID" value={worker.worker_reference_id} /><Value name="Worker owner" value={worker.owner_operator_id} /><Value name="Worker kind" value={worker.worker_kind} /><Value name="Worker trust domain" value={worker.trust_domain} /><Value name="Worker scope" value={worker.scope} /><Value name="Worker eligibility" value={worker.eligibility} /><Value name="Worker identity fingerprint" value={worker.identity_fingerprint.value} /><Value name="Worker capability fingerprint" value={worker.capability_profile_fingerprint.value} /><Value name="Worker reference fingerprint" value={worker.reference_fingerprint.value} /><Value name="Worker valid from" value={worker.valid_from} /><Value name="Worker valid until" value={worker.valid_until} />
                <Value name="Admission intent ID" value={intent.intent_id} /><Value name="Admission intent" value={intent.intent} /><Value name="Intake state" value={intake.intake_state} /><Value name="Intake protocol" value={intake.intake_protocol} /><Value name="Intent fingerprint" value={intent.intent_fingerprint.value} /><Value name="Intake fingerprint" value={intake.intake_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Blockers</h6>
            <ol aria-label="Ordered worker admission blockers" className="mt-2 list-decimal pl-5">{stub.blockers.map((blocker) => <li key={blocker}>{BLOCKERS[blocker]} <code className="text-xs text-slate-400">{blocker}</code></li>)}</ol>
            <h6 className="mt-3 font-semibold">Inherited byte-exact sandbox, resource, network, and filesystem ceilings</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} /><Value name="Privileged / escalation / host namespaces / devices" value="false" /><Value name="Drop all capabilities" value="true" /><Value name="Seccomp / AppArmor required" value="true" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} /><Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} /><Value name="PID ceiling" value={String(limits.resources.pids_max)} /><Value name="Wall-time ceiling (seconds)" value={String(limits.resources.wall_time_seconds_max)} /><Value name="Output ceiling (bytes)" value={String(limits.resources.output_bytes_max)} />
                <Value name="Network mode" value={limits.network.mode} /><Value name="Ingress / egress / DNS / image pull" value="false" /><Value name="Allowed endpoint fingerprints" value="none" />
                <Value name="Root filesystem read-only" value="true" /><Value name="Host/repository/guest mounts" value="false" /><Value name="Writable scope" value={limits.filesystem.writable_scope} /><Value name="Ephemeral workspace ceiling (bytes)" value={String(limits.filesystem.ephemeral_workspace_bytes_max)} /><Value name="Inherited limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Required v0.20-v0.37 linkage and runner binding evidence</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="v0.20-v0.36 chain fingerprint" value={linkage.v020_v036_chain_fingerprint.value} /><Value name="v0.34 readiness review fingerprint" value={linkage.readiness_review_fingerprint.value} /><Value name="v0.35 permission grant fingerprint" value={linkage.permission_grant_fingerprint.value} /><Value name="v0.36 execution admission fingerprint" value={linkage.execution_admission_fingerprint.value} /><Value name="v0.37 runner binding plan ID" value={linkage.runner_binding_plan_id} /><Value name="v0.37 runner binding plan fingerprint" value={linkage.runner_binding_plan_fingerprint.value} /><Value name="v0.37 runner binding status fingerprint" value={linkage.runner_binding_plan_status_fingerprint.value} /><Value name="Runner reference fingerprint" value={linkage.runner_reference_fingerprint.value} /><Value name="Worker intent fingerprint" value={linkage.worker_admission_intent_fingerprint.value} /><Value name="Worker intake fingerprint" value={linkage.worker_admission_intake_fingerprint.value} /><Value name="Linkage fingerprint" value={linkage.linkage_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Audit and authority</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value name="Request fingerprint" value={stub.request_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={stub.idempotency_key_fingerprint.value} /><Value name="Audit event" value={audit.event} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit fingerprint" value={audit.audit_fingerprint.value} /><Value name="Correlation fingerprint" value={audit.correlation_fingerprint.value} /></dl>
            <p className="mt-3 text-xs">Permanent worker-admission-subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · retry allowed: false · replay allowed: false.</p>
            <dl aria-label="Worker admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Runner binding allowed", "Worker registered", "Worker contacted", "Worker reserved", "Worker bound", "Worker started", "Queue created", "Queue allowed", "Work enqueued", "Enqueue allowed", "Dispatch allowed", "Execution start allowed", "Execution authorized", "Installation allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        </details>
        <WorkerQueueReservations candidateId={candidateId} stubId={stub.stub_id} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
