import { useEffect, useState } from "react";

import { listRunnerBindingPlans } from "../../api/runnerBindingPlan";
import type { InstallationExecutionAdmissionResultV1 } from "../../types/installationExecutionAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { RunnerBindingPlanResultV1 } from "../../types/runnerBindingPlan";
import { WorkerAdmissionStubs } from "./WorkerAdmissionStubs";

const BLOCKER_LABELS: Record<string, string> = {
    runner_not_bound: "No machine is connected to this plan.",
    execution_start_boundary_not_defined: "Atlas has not set up a safe way to start this installation yet.",
};

export function RunnerBindingPlans({ candidateId, admission, homeAssistantBlocked }: { candidateId: string; admission: InstallationExecutionAdmissionResultV1; homeAssistantBlocked: boolean }) {
    const [plans, setPlans] = useState<RunnerBindingPlanResultV1[] | null>(null);
    const [error, setError] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);
    useEffect(() => {
        let current = true;
        listRunnerBindingPlans(candidateId)
            .then((value) => { if (current) setPlans(value.plans.filter((item) => item.plan?.linkage.execution_admission_id === admission.admission?.admission_id)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, admission.admission?.admission_id, readAttempt]);

    return <section aria-labelledby={`runner-binding-plans-${admission.admission?.admission_id}`} className="mt-4 rounded border border-slate-700 p-4">
        <h4 id={`runner-binding-plans-${admission.admission?.admission_id}`} className="font-semibold">Machine setup plan</h4>
        <p className="mt-2 text-sm">This review record does not connect a machine or start an installation.</p>
        <p className="mt-2 text-sm">Atlas has no eligible machine to reference here, so it cannot create a setup plan. It does not search for or contact machines.</p>
        {homeAssistantBlocked && <p className="mt-3 text-sm text-amber-200">Atlas cannot install or run Home Assistant yet.</p>}
        {plans === null && !error && <p role="status" className="mt-4">Checking for a saved machine setup plan…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>Atlas could not load the machine setup plan. Retry to check its current status.</p><p className="text-xs text-slate-400">Private system details are hidden.</p><button type="button" onClick={() => { setPlans(null); setError(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {plans?.length === 0 && <p role="status" className="mt-4">No machine setup plan has been saved. Atlas cannot start an installation.</p>}
        {plans && plans.length > 0 && <ol aria-label="Saved machine setup plans" className="mt-4 space-y-4">{plans.map((item) => <Plan key={item.plan!.plan_id} result={item} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Plan({ result, homeAssistantBlocked }: { result: RunnerBindingPlanResultV1; homeAssistantBlocked: boolean }) {
    const plan = result.plan!; const status = result.status!; const audit = result.audit_evidence!;
    const reference = plan.runner_reference; const limits = plan.limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h5 className="font-semibold">{status.lifecycle === "active" ? "Machine setup plan is current" : "Machine setup plan has expired"}</h5>
        <p className="mt-1">This is a review record, not a live machine connection. Atlas has not contacted or connected to a machine.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(plan.recorded_at)}; valid until {formatUtcTimestamp(plan.valid_until)}; checked {formatUtcTimestamp(status.observed_at)}. An expired plan cannot be renewed.</p>
        <ol aria-label="What needs attention" className="mt-2 list-decimal pl-5">{plan.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker] ?? "Atlas reported an issue that needs review."}</li>)}</ol>
        <details className="mt-3">
            <summary className="cursor-pointer text-xs text-slate-400">Technical details</summary>
            <p className="mt-2">Plan status: {plan.eligibility}; record state: {plan.record_state}; result: {result.disposition}.</p>
            <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                <Value name="Authenticated operator" value={plan.operator_id} /><Value name="Plan ID" value={plan.plan_id} /><Value name="Plan fingerprint" value={plan.plan_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} />
                <Value name="Machine reference ID" value={reference.runner_reference_id} /><Value name="Machine owner" value={reference.owner_operator_id} /><Value name="Machine type" value={reference.runner_kind} /><Value name="Machine eligibility" value={reference.eligibility} /><Value name="Machine identity fingerprint" value={reference.identity_fingerprint.value} /><Value name="Machine capability fingerprint" value={reference.capability_profile_fingerprint.value} /><Value name="Machine reference fingerprint" value={reference.reference_fingerprint.value} /><Value name="Machine valid from" value={reference.valid_from} /><Value name="Machine valid until" value={reference.valid_until} />
            </dl>
            <details className="mt-3"><summary>Sandbox and resource limits</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} /><Value name="Privileged" value="false" /><Value name="Privilege escalation" value="false" /><Value name="Host namespaces/devices" value="false" /><Value name="Drop all capabilities" value="true" /><Value name="Seccomp required" value="true" /><Value name="AppArmor required" value="true" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} /><Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} /><Value name="PID ceiling" value={String(limits.resources.pids_max)} /><Value name="Wall-time ceiling (seconds)" value={String(limits.resources.wall_time_seconds_max)} /><Value name="Output ceiling (bytes)" value={String(limits.resources.output_bytes_max)} />
                <Value name="Network mode" value={limits.network.mode} /><Value name="Ingress / egress / DNS / image pull" value="false" /><Value name="Allowed endpoint fingerprints" value="none" />
                <Value name="Root filesystem read-only" value="true" /><Value name="Host/repository/guest mounts" value="false" /><Value name="Writable scope" value={limits.filesystem.writable_scope} /><Value name="Ephemeral workspace ceiling (bytes)" value={String(limits.filesystem.ephemeral_workspace_bytes_max)} /><Value name="Limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl></details>
            <details className="mt-3"><summary>Related review records</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="v0.20–v0.35 chain fingerprint" value={plan.linkage.v020_v035_chain_fingerprint.value} /><Value name="v0.34 readiness review fingerprint" value={plan.linkage.readiness_review_fingerprint.value} /><Value name="v0.35 permission grant fingerprint" value={plan.linkage.permission_grant_fingerprint.value} /><Value name="v0.36 execution admission ID" value={plan.linkage.execution_admission_id} /><Value name="v0.36 execution admission fingerprint" value={plan.linkage.execution_admission_fingerprint.value} /><Value name="v0.36 admission status fingerprint" value={plan.linkage.execution_admission_status_fingerprint.value} /><Value name="Machine reference fingerprint" value={plan.linkage.runner_reference_fingerprint.value} /><Value name="Machine identity fingerprint" value={plan.linkage.runner_identity_fingerprint.value} /><Value name="Machine capability fingerprint" value={plan.linkage.runner_capability_profile_fingerprint.value} /><Value name="Linkage fingerprint" value={plan.linkage.linkage_fingerprint.value} />
            </dl></details>
            <dl className="mt-3 grid gap-2 sm:grid-cols-2"><Value name="Request fingerprint" value={plan.request_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={plan.idempotency_key_fingerprint.value} /><Value name="Audit event" value={audit.event} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit fingerprint" value={audit.audit_fingerprint.value} /><Value name="Correlation fingerprint" value={audit.correlation_fingerprint.value} /></dl>
            <p className="mt-3 text-xs">This record cannot be retried or replayed.</p>
            <details className="mt-3"><summary>Authority flags</summary><dl aria-label="Runner binding fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Runner registered", "Runner contacted", "Runner reserved", "Runner bound", "Runner binding allowed", "Execution start allowed", "Execution authorized", "Installation allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl></details>
        </details>
        <WorkerAdmissionStubs candidateId={plan.candidate_record_id} bindingPlan={result} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
