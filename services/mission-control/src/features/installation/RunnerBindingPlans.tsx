import { useEffect, useState } from "react";

import { listRunnerBindingPlans } from "../../api/runnerBindingPlan";
import type { InstallationExecutionAdmissionResultV1 } from "../../types/installationExecutionAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { RunnerBindingPlanResultV1, RunnerBindingPlanV1 } from "../../types/runnerBindingPlan";
import { WorkerAdmissionStubs } from "./WorkerAdmissionStubs";

const BLOCKER_LABELS: Record<RunnerBindingPlanV1["blockers"][number], string> = {
    runner_not_bound: "No runner is bound to this plan",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
};

export function RunnerBindingPlans({ candidateId, admission, homeAssistantBlocked }: { candidateId: string; admission: InstallationExecutionAdmissionResultV1; homeAssistantBlocked: boolean }) {
    const [plans, setPlans] = useState<RunnerBindingPlanResultV1[] | null>(null);
    const [error, setError] = useState(false);
    useEffect(() => {
        let current = true;
        listRunnerBindingPlans(candidateId)
            .then((value) => { if (current) setPlans(value.plans.filter((item) => item.plan?.linkage.execution_admission_id === admission.admission?.admission_id)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, admission.admission?.admission_id]);

    return <section aria-labelledby={`runner-binding-plans-${admission.admission?.admission_id}`} className="mt-4 rounded border border-slate-700 p-4">
        <h4 id={`runner-binding-plans-${admission.admission?.admission_id}`} className="font-semibold">Runner setup review</h4>
        <p className="mt-2 text-sm">A saved plan lists limits a future runner would have to follow. It does not select or contact a runner, authorize installation, or start work.</p>
        <p className="mt-2 text-sm text-slate-400">No runner is available to bind from this review. Mission Control does not discover, register, or contact runners.</p>
        {homeAssistantBlocked && <p className="mt-3 text-sm text-amber-200">Atlas cannot install Home Assistant, so it cannot be prepared for a runner.</p>}
        {plans === null && !error && <p role="status" className="mt-4">Loading saved runner plans…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>Saved runner plans could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {plans?.length === 0 && <p role="status" className="mt-4">No runner plan is saved. No runner is bound, and installation cannot start.</p>}
        {plans && plans.length > 0 && <ol aria-label="Saved runner plans" className="mt-4 space-y-4">{plans.map((item) => <Plan key={item.plan!.plan_id} result={item} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Plan({ result, homeAssistantBlocked }: { result: RunnerBindingPlanResultV1; homeAssistantBlocked: boolean }) {
    const plan = result.plan!; const status = result.status!; const audit = result.audit_evidence!;
    const reference = plan.runner_reference; const limits = plan.limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h5 className="font-semibold">{status.lifecycle === "active" ? "Saved runner plan" : "Expired runner plan"}</h5>
        <p className="mt-1">This plan does not register, contact, reserve, or bind a runner. It does not authorize or start installation.</p>
        <p className="mt-1">Saved {plan.recorded_at}; expires {plan.valid_until}.</p>
        <h6 className="mt-3 text-sm font-medium">What still needs to be in place</h6>
        <ul aria-label="What still needs to be in place" className="mt-2 list-disc pl-5">{plan.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker]}</li>)}</ul>
        <ul aria-label="Planned safety limits" className="mt-3 list-disc pl-5 text-sm text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Exact sandbox and resource limits</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">
            <Value name="Sandbox profile" value={limits.sandbox.profile} /><Value name="Privileged" value="false" /><Value name="Privilege escalation" value="false" /><Value name="Host namespaces and devices" value="false" /><Value name="Drop all capabilities" value="true" /><Value name="Seccomp required" value="true" /><Value name="AppArmor required" value="true" />
            <Value name="CPU ceiling (millicores)" value={String(limits.resources.cpu_millis_max)} /><Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} /><Value name="PID ceiling" value={String(limits.resources.pids_max)} /><Value name="Wall-time ceiling (seconds)" value={String(limits.resources.wall_time_seconds_max)} /><Value name="Output ceiling (bytes)" value={String(limits.resources.output_bytes_max)} />
            <Value name="Network mode" value={limits.network.mode} /><Value name="Ingress, egress, DNS, image pull" value="false" /><Value name="Allowed endpoint fingerprints" value="none" />
            <Value name="Root filesystem read-only" value="true" /><Value name="Host, repository, and guest mounts" value="false" /><Value name="Writable scope" value={limits.filesystem.writable_scope} /><Value name="Temporary workspace ceiling (bytes)" value={String(limits.filesystem.ephemeral_workspace_bytes_max)} /><Value name="Limits fingerprint" value={limits.limits_fingerprint.value} />
        </dl></details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Plan identity and linked evidence</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">
            <Value name="Authenticated operator" value={plan.operator_id} /><Value name="Candidate record ID" value={plan.candidate_record_id} /><Value name="Plan ID" value={plan.plan_id} /><Value name="Plan fingerprint" value={plan.plan_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} />
            <Value name="Runner reference ID" value={reference.runner_reference_id} /><Value name="Runner owner" value={reference.owner_operator_id} /><Value name="Runner kind code" value={reference.runner_kind} /><Value name="Runner eligibility code" value={reference.eligibility} /><Value name="Runner identity fingerprint" value={reference.identity_fingerprint.value} /><Value name="Runner capability fingerprint" value={reference.capability_profile_fingerprint.value} /><Value name="Runner reference fingerprint" value={reference.reference_fingerprint.value} /><Value name="Runner valid from" value={reference.valid_from} /><Value name="Runner valid until" value={reference.valid_until} />
            <Value name="Eligibility code" value={plan.eligibility} /><Value name="Lifecycle code" value={status.lifecycle} /><Value name="Disposition code" value={result.disposition} /><Value name="Record state code" value={plan.record_state} /><Value name="Observed at" value={status.observed_at} />
            <Value name="v0.20–v0.35 evidence chain fingerprint" value={plan.linkage.v020_v035_chain_fingerprint.value} /><Value name="Readiness review fingerprint" value={plan.linkage.readiness_review_fingerprint.value} /><Value name="Permission record fingerprint" value={plan.linkage.permission_grant_fingerprint.value} /><Value name="Execution admission ID" value={plan.linkage.execution_admission_id} /><Value name="Execution admission fingerprint" value={plan.linkage.execution_admission_fingerprint.value} /><Value name="Admission status fingerprint" value={plan.linkage.execution_admission_status_fingerprint.value} /><Value name="Runner reference fingerprint" value={plan.linkage.runner_reference_fingerprint.value} /><Value name="Runner identity fingerprint" value={plan.linkage.runner_identity_fingerprint.value} /><Value name="Runner capability fingerprint" value={plan.linkage.runner_capability_profile_fingerprint.value} /><Value name="Linkage fingerprint" value={plan.linkage.linkage_fingerprint.value} />
        </dl></details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Audit and authority details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value name="Request fingerprint" value={plan.request_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={plan.idempotency_key_fingerprint.value} /><Value name="Audit event" value={audit.event} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit fingerprint" value={audit.audit_fingerprint.value} /><Value name="Correlation fingerprint" value={audit.correlation_fingerprint.value} /></dl>
            <p className="mt-3 text-xs">Binding and idempotency use are reserved permanently. The raw key is not saved, and this record cannot be retried or replayed.</p>
            <dl aria-label="Runner binding fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Runner registered", "Runner contacted", "Runner reserved", "Runner bound", "Runner binding allowed", "Execution start allowed", "Execution authorized", "Installation allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        </details>
        <WorkerAdmissionStubs candidateId={plan.candidate_record_id} bindingPlan={result} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
