import { useEffect, useState } from "react";

import { listWorkerAdmissionStubs } from "../../api/workerAdmissionStub";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { RunnerBindingPlanResultV1 } from "../../types/runnerBindingPlan";
import type { WorkerAdmissionStubResultV1, WorkerAdmissionStubV1 } from "../../types/workerAdmissionStub";
import { WorkerQueueReservations } from "./WorkerQueueReservations";

const BLOCKERS: Record<WorkerAdmissionStubV1["blockers"][number], string> = {
    worker_not_started: "A worker has not been started",
    queue_boundary_not_defined: "A safe way to create or use a work queue is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
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
        <h5 id={`worker-admission-stubs-${bindingPlan.plan?.plan_id}`} className="font-semibold">Worker review</h5>
        <p className="mt-2 text-sm">This record keeps a worker under consideration for a later review. It does not contact or start a worker, create a queue, or authorize installation.</p>
        <p className="mt-2 text-sm text-slate-400">No worker is available to this review. Mission Control does not discover or contact workers.</p>
        {homeAssistantBlocked && <p className="mt-3 text-sm text-amber-200">Atlas cannot install Home Assistant, so it cannot be prepared for a worker.</p>}
        {stubs === null && !error && <p role="status" className="mt-4">Loading saved worker review records…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>Saved worker review records could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {stubs?.length === 0 && <p role="status" className="mt-4">No worker review record is saved. No worker has started, and no work has been queued.</p>}
        {stubs && stubs.length > 0 && <ol aria-label="Saved worker review records" className="mt-4 space-y-4">{stubs.map((item) => <Stub key={item.stub!.stub_id} result={item} candidateId={candidateId} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Stub({ result, candidateId, homeAssistantBlocked }: { result: WorkerAdmissionStubResultV1; candidateId: string; homeAssistantBlocked: boolean }) {
    const stub = result.stub!; const status = result.status!; const audit = result.audit_evidence!;
    const worker = stub.worker_reference; const intent = stub.worker_admission_intent; const intake = stub.worker_admission_intake; const limits = stub.inherited_limits; const linkage = stub.linkage;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status.lifecycle === "active" ? "Saved worker review record" : "Expired worker review record"}</h6>
        <p className="mt-1">This record has not started a worker or queued work. It does not authorize installation or execution.</p>
        <p className="mt-1">Saved <time dateTime={stub.recorded_at}>{formatDateTime(stub.recorded_at)}</time>; expires <time dateTime={stub.valid_until}>{formatDateTime(stub.valid_until)}</time>.</p>
        <h6 className="mt-3 font-semibold">What still needs to be in place</h6>
        <ul aria-label="What still needs to be in place" className="mt-2 list-disc pl-5">{stub.blockers.map((blocker) => <li key={blocker}>{BLOCKERS[blocker]}</li>)}</ul>
        <ul aria-label="Planned worker safety limits" className="mt-3 list-disc pl-5 text-sm text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Worker and record details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Eligibility" value={stub.eligibility} /><Value name="Lifecycle" value={status.lifecycle} /><Value name="Disposition" value={result.disposition} /><Value name="Record state" value={stub.record_state} />
                <Value name="Authenticated operator" value={stub.operator_id} /><Value name="Stub ID" value={stub.stub_id} /><Value name="Stub fingerprint" value={stub.stub_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} />
                <Value name="Worker reference ID" value={worker.worker_reference_id} /><Value name="Worker owner" value={worker.owner_operator_id} /><Value name="Worker kind" value={worker.worker_kind} /><Value name="Worker trust domain" value={worker.trust_domain} /><Value name="Worker scope" value={worker.scope} /><Value name="Worker eligibility" value={worker.eligibility} /><Value name="Worker identity fingerprint" value={worker.identity_fingerprint.value} /><Value name="Worker capability fingerprint" value={worker.capability_profile_fingerprint.value} /><Value name="Worker reference fingerprint" value={worker.reference_fingerprint.value} /><Value name="Worker valid from" value={worker.valid_from} /><Value name="Worker valid until" value={worker.valid_until} />
                <Value name="Admission intent ID" value={intent.intent_id} /><Value name="Admission intent" value={intent.intent} /><Value name="Intake state" value={intake.intake_state} /><Value name="Intake protocol" value={intake.intake_protocol} /><Value name="Intent fingerprint" value={intent.intent_fingerprint.value} /><Value name="Intake fingerprint" value={intake.intake_fingerprint.value} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Exact safety limits and earlier evidence</summary>
            <h6 className="mt-2 font-medium">Exact sandbox and resource limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} /><Value name="Privileged / escalation / host namespaces / devices" value="false" /><Value name="Drop all capabilities" value="true" /><Value name="Seccomp / AppArmor required" value="true" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} /><Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} /><Value name="PID ceiling" value={String(limits.resources.pids_max)} /><Value name="Wall-time ceiling (seconds)" value={String(limits.resources.wall_time_seconds_max)} /><Value name="Output ceiling (bytes)" value={String(limits.resources.output_bytes_max)} />
                <Value name="Network mode" value={limits.network.mode} /><Value name="Ingress / egress / DNS / image pull" value="false" /><Value name="Allowed endpoint fingerprints" value="none" />
                <Value name="Root filesystem read-only" value="true" /><Value name="Host/repository/guest mounts" value="false" /><Value name="Writable scope" value={limits.filesystem.writable_scope} /><Value name="Ephemeral workspace ceiling (bytes)" value={String(limits.filesystem.ephemeral_workspace_bytes_max)} /><Value name="Inherited limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-medium">Earlier evidence linked to this record</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Prior evidence chain fingerprint" value={linkage.v020_v036_chain_fingerprint.value} /><Value name="Readiness review fingerprint" value={linkage.readiness_review_fingerprint.value} /><Value name="Permission record fingerprint" value={linkage.permission_grant_fingerprint.value} /><Value name="Execution admission fingerprint" value={linkage.execution_admission_fingerprint.value} /><Value name="Runner plan ID" value={linkage.runner_binding_plan_id} /><Value name="Runner plan fingerprint" value={linkage.runner_binding_plan_fingerprint.value} /><Value name="Runner plan status fingerprint" value={linkage.runner_binding_plan_status_fingerprint.value} /><Value name="Runner reference fingerprint" value={linkage.runner_reference_fingerprint.value} /><Value name="Worker intent fingerprint" value={linkage.worker_admission_intent_fingerprint.value} /><Value name="Worker intake fingerprint" value={linkage.worker_admission_intake_fingerprint.value} /><Value name="Linkage fingerprint" value={linkage.linkage_fingerprint.value} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Audit and authority details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value name="Request fingerprint" value={stub.request_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={stub.idempotency_key_fingerprint.value} /><Value name="Audit event" value={audit.event} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit fingerprint" value={audit.audit_fingerprint.value} /><Value name="Correlation fingerprint" value={audit.correlation_fingerprint.value} /></dl>
            <p className="mt-3 text-xs">Worker and idempotency use are reserved permanently. The raw key is not saved, and this record cannot be retried or replayed.</p>
            <dl aria-label="Worker admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Runner binding allowed", "Worker registered", "Worker contacted", "Worker reserved", "Worker bound", "Worker started", "Queue created", "Queue allowed", "Work enqueued", "Enqueue allowed", "Dispatch allowed", "Execution start allowed", "Execution authorized", "Installation allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        </details>
        <WorkerQueueReservations candidateId={candidateId} stubId={stub.stub_id} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
