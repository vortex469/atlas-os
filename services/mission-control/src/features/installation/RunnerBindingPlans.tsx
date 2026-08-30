import { useEffect, useState } from "react";

import { listRunnerBindingPlans } from "../../api/runnerBindingPlan";
import type { InstallationExecutionAdmissionResultV1 } from "../../types/installationExecutionAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { RunnerBindingPlanResultV1 } from "../../types/runnerBindingPlan";

const BLOCKER_LABELS: Record<string, string> = {
    runner_not_bound: "Runner is not bound",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
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
        <h4 id={`runner-binding-plans-${admission.admission?.admission_id}`} className="font-semibold">Runner binding plan evidence</h4>
        <p className="mt-2 text-sm">This records a runner binding plan only. It does not bind or contact a runner and does not authorize or start installation or execution.</p>
        <p className="mt-2 text-sm">A binding_planned record is evidence only. It is not actual runner binding, worker start, execution start, install, dispatch, retry or resend, Agent invocation, workflow start, Docker, Podman, shell or process execution, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or mutation authority.</p>
        <p className="mt-2 text-sm">Creation is unavailable in this context because Core exposes no eligible runner reference here. Mission Control does not discover runners, invent identities, edit ceilings, or contact a runner. The guarded v0.37 create boundary remains the only permitted plan mutation.</p>
        {homeAssistantBlocked && <p className="mt-3 text-sm text-amber-200">Home Assistant remains blocked, non-installable, non-executable, and ineligible for runner binding planning.</p>}
        {plans === null && !error && <p role="status" className="mt-4">Loading runner binding plan evidence…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>Runner binding plan evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no provider payload, credential, command, log, endpoint, address, mount source, or internal path is shown.</p></div>}
        {plans?.length === 0 && <p role="status" className="mt-4">No runner binding plan evidence has been recorded. Runner binding and execution remain blocked.</p>}
        {plans && plans.length > 0 && <ol aria-label="Runner binding plans" className="mt-4 space-y-4">{plans.map((item) => <Plan key={item.plan!.plan_id} result={item} />)}</ol>}
    </section>;
}

function Plan({ result }: { result: RunnerBindingPlanResultV1 }) {
    const plan = result.plan!; const status = result.status!; const audit = result.audit_evidence!;
    const reference = plan.runner_reference; const limits = plan.limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h5 className="font-semibold">{status.lifecycle === "active" ? "Active binding-planned evidence" : "Expired binding-planned evidence"}</h5>
        <p className="mt-1">Eligibility: {plan.eligibility}; lifecycle: {status.lifecycle}; disposition: {result.disposition}; record state: {plan.record_state}.</p>
        <p className="mt-1">Recorded {plan.recorded_at}; valid until {plan.valid_until}; observed {status.observed_at}. Freshness is inherited for at most 30 seconds. Expiry never refreshes or reauthorizes evidence.</p>
        <ol aria-label="Ordered runner binding blockers" className="mt-2 list-decimal pl-5">{plan.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker]} <code className="text-xs text-slate-400">{blocker}</code></li>)}</ol>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            <Value name="Authenticated operator" value={plan.operator_id} /><Value name="Plan ID" value={plan.plan_id} /><Value name="Plan fingerprint" value={plan.plan_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} />
            <Value name="Runner reference ID" value={reference.runner_reference_id} /><Value name="Runner owner" value={reference.owner_operator_id} /><Value name="Runner kind" value={reference.runner_kind} /><Value name="Runner eligibility" value={reference.eligibility} /><Value name="Runner identity fingerprint" value={reference.identity_fingerprint.value} /><Value name="Runner capability fingerprint" value={reference.capability_profile_fingerprint.value} /><Value name="Runner reference fingerprint" value={reference.reference_fingerprint.value} /><Value name="Runner valid from" value={reference.valid_from} /><Value name="Runner valid until" value={reference.valid_until} />
        </dl>
        <details className="mt-3" open><summary>Sandbox, resource, network, and filesystem ceilings</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">
            <Value name="Sandbox profile" value={limits.sandbox.profile} /><Value name="Privileged" value="false" /><Value name="Privilege escalation" value="false" /><Value name="Host namespaces/devices" value="false" /><Value name="Drop all capabilities" value="true" /><Value name="Seccomp required" value="true" /><Value name="AppArmor required" value="true" />
            <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} /><Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} /><Value name="PID ceiling" value={String(limits.resources.pids_max)} /><Value name="Wall-time ceiling (seconds)" value={String(limits.resources.wall_time_seconds_max)} /><Value name="Output ceiling (bytes)" value={String(limits.resources.output_bytes_max)} />
            <Value name="Network mode" value={limits.network.mode} /><Value name="Ingress / egress / DNS / image pull" value="false" /><Value name="Allowed endpoint fingerprints" value="none" />
            <Value name="Root filesystem read-only" value="true" /><Value name="Host/repository/guest mounts" value="false" /><Value name="Writable scope" value={limits.filesystem.writable_scope} /><Value name="Ephemeral workspace ceiling (bytes)" value={String(limits.filesystem.ephemeral_workspace_bytes_max)} /><Value name="Limits fingerprint" value={limits.limits_fingerprint.value} />
        </dl></details>
        <details className="mt-3"><summary>Required v0.20–v0.36 linkage and admission evidence</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">
            <Value name="v0.20–v0.35 chain fingerprint" value={plan.linkage.v020_v035_chain_fingerprint.value} /><Value name="v0.34 readiness review fingerprint" value={plan.linkage.readiness_review_fingerprint.value} /><Value name="v0.35 permission grant fingerprint" value={plan.linkage.permission_grant_fingerprint.value} /><Value name="v0.36 execution admission ID" value={plan.linkage.execution_admission_id} /><Value name="v0.36 execution admission fingerprint" value={plan.linkage.execution_admission_fingerprint.value} /><Value name="v0.36 admission status fingerprint" value={plan.linkage.execution_admission_status_fingerprint.value} /><Value name="Runner reference fingerprint" value={plan.linkage.runner_reference_fingerprint.value} /><Value name="Runner identity fingerprint" value={plan.linkage.runner_identity_fingerprint.value} /><Value name="Runner capability fingerprint" value={plan.linkage.runner_capability_profile_fingerprint.value} /><Value name="Linkage fingerprint" value={plan.linkage.linkage_fingerprint.value} />
        </dl></details>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2"><Value name="Request fingerprint" value={plan.request_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={plan.idempotency_key_fingerprint.value} /><Value name="Audit event" value={audit.event} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit fingerprint" value={audit.audit_fingerprint.value} /><Value name="Correlation fingerprint" value={audit.correlation_fingerprint.value} /></dl>
        <p className="mt-3 text-xs">Permanent binding-subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · retry allowed: false · replay allowed: false.</p>
        <dl aria-label="Runner binding fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Runner registered", "Runner contacted", "Runner reserved", "Runner bound", "Runner binding allowed", "Execution start allowed", "Execution authorized", "Installation allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
