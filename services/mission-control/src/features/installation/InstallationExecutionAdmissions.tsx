import { useEffect, useState } from "react";

import { createInstallationExecutionAdmission, installationExecutionAdmissionIdempotencyKey, listInstallationExecutionAdmissions } from "../../api/installationExecutionAdmission";
import { LINKAGE_KEYS } from "../../api/installationReadinessReview";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ExecutionPermissionGrantResultV1 } from "../../types/executionPermissionGrant";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { InstallationExecutionAdmissionCreateV1, InstallationExecutionAdmissionResultV1 } from "../../types/installationExecutionAdmission";
import { RunnerBindingPlans } from "./RunnerBindingPlans";

const BLOCKER_LABELS: Record<string, string> = {
    runner_binding_not_defined: "No machine is set up to run this installation yet.",
    execution_start_boundary_not_defined: "Atlas has not set up a safe way to start this installation yet.",
    installation_capability_unsupported: "Atlas cannot install this type of item yet.",
    stale_evidence: "Some information is out of date.", expired_evidence: "Some information has expired.",
    grant_not_active: "The saved confirmation is no longer current.",
    grant_scope_mismatch: "The saved confirmation does not match this review.",
};

export function InstallationExecutionAdmissions({ candidateId, grants, homeAssistantBlocked }: { candidateId: string; grants: ExecutionPermissionGrantResultV1[]; homeAssistantBlocked: boolean }) {
    const session = useOperatorSession();
    const [admissions, setAdmissions] = useState<InstallationExecutionAdmissionResultV1[] | null>(null);
    const [error, setError] = useState<"load" | "create" | null>(null);
    const [readAttempt, setReadAttempt] = useState(0);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    useEffect(() => {
        let current = true;
        listInstallationExecutionAdmissions(candidateId).then((value) => { if (current) setAdmissions(value.admissions); }).catch(() => { if (current) setError("load"); });
        return () => { current = false; };
    }, [candidateId, readAttempt]);

    const activeGrant = grants.find((item) => item.grant && item.status?.lifecycle === "active");
    const mayCreate = admissions !== null && admissions.length === 0 && error === null &&
        !homeAssistantBlocked && Boolean(activeGrant) && session.authenticated &&
        session.principal?.permissions.includes("installation.execution.admission.record") &&
        Boolean(session.csrfToken);
    const record = async () => {
        if (!session.csrfToken || !activeGrant?.grant || submitting) return;
        setSubmitting(true); setError(null);
        const grant = activeGrant.grant;
        const body: InstallationExecutionAdmissionCreateV1 = {
            schema: "installation-execution-admission-create-v1",
            permission_grant_id: grant.grant_id,
            permission_grant_fingerprint: grant.grant_fingerprint,
            grant_valid_until: grant.valid_until,
            requested_scope: "future_installation_runner_consideration_only",
            runner_eligibility_claim: "evidence_chain_only_no_runner_selected",
            execution_authorized: false, installation_allowed: false,
            dispatch_allowed: false, worker_allowed: false,
            mutation_allowed: false, replay_allowed: false,
        };
        try {
            const result = await createInstallationExecutionAdmission(candidateId, body, session.csrfToken, installationExecutionAdmissionIdempotencyKey());
            if (!result.admission || !result.status || !result.audit_evidence) {
                setError("create"); setConfirming(false); return;
            }
            setAdmissions((current) => [result, ...(current ?? [])]); setConfirming(false);
        } catch { setError("create"); setConfirming(false); }
        finally { setSubmitting(false); }
    };

    return <section aria-labelledby="execution-admissions-heading" className="mt-6 rounded border border-slate-700 p-4">
        <h2 id="execution-admissions-heading" className="font-semibold">Installation run review</h2>
        <p className="mt-2 text-sm">This records a review step only. It does not pick a machine, install anything, or start work.</p>
        <details className="mt-2">
            <summary className="cursor-pointer text-xs text-slate-400">How this record works</summary>
            <p className="mt-2 text-sm">This record is evidence only. It does not connect a machine, start work, or allow system changes.</p>
            <p className="mt-2 text-sm">It is tied to this operator and the exact earlier reviews and confirmation. If it expires, it cannot be renewed or reused.</p>
        </details>
        {admissions === null && !error && <p role="status" className="mt-4">Checking for saved run review records…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>{error === "load" ? "Atlas could not load the run review record. Retry to check its current status." : "Atlas could not save the run review record."}</p><p className="text-xs text-slate-400">Private system details are hidden.</p>{error === "load" && <button type="button" onClick={() => { setAdmissions(null); setError(null); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button>}</div>}
        {admissions?.length === 0 && !error && <p role="status" className="mt-4">No run review record has been saved.</p>}
        {admissions && admissions.length > 0 && <ol aria-label="Saved run review records" className="mt-4 space-y-4">{admissions.map((item) => <Admission key={item.admission!.admission_id} result={item} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-4 rounded border border-blue-400 px-3 py-2 text-sm">Review run statement</button>}
        {mayCreate && confirming && <div aria-label="Run review confirmation" className="mt-4 rounded border border-amber-400/40 p-4">
            <p className="font-semibold">Step 2 of 2 — save the review record</p>
            <p className="mt-2 text-sm">This saves the review only. It does not choose a machine or allow an installation to start.</p>
            <p className="mt-2 text-xs">The record stays for review only and cannot be replayed.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Save review record</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {admissions?.length === 0 && !error && !mayCreate && <p className="mt-4 text-sm text-amber-200">A current confirmation and an operator account with permission are needed before a run review record can be saved.</p>}
        {!mayCreate && homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">Atlas cannot install or run Home Assistant yet.</p>}
    </section>;
}

function Admission({ result, homeAssistantBlocked }: { result: InstallationExecutionAdmissionResultV1; homeAssistantBlocked: boolean }) {
    const admission = result.admission!; const status = result.status!; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h3 className="font-semibold">{status.lifecycle === "active" ? "Run review record is current" : "Run review record has expired"}</h3>
        <p className="mt-1">This record is for review only. Atlas has not picked a machine to run the work.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(admission.recorded_at)}; valid until {formatUtcTimestamp(admission.valid_until)}; checked {formatUtcTimestamp(status.observed_at)}. An expired record cannot be renewed.</p>
        <ol aria-label="What needs attention" className="mt-2 list-decimal pl-5">{admission.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker] ?? "Atlas reported an issue that needs review."}</li>)}</ol>
        <details className="mt-3">
            <summary className="cursor-pointer text-xs text-slate-400">Technical details</summary>
            <p className="mt-2">Readiness: {admission.readiness}; lifecycle: {status.lifecycle}; disposition: {result.disposition}; record state: {admission.record_state}.</p>
            <dl className="mt-3 grid gap-2 sm:grid-cols-2"><Value name="Authenticated operator" value={admission.operator_id} /><Value name="Admission ID" value={admission.admission_id} /><Value name="Admission fingerprint" value={admission.admission_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} /><Value name="v0.35 permission grant ID" value={admission.linkage.v035_grant_id} /><Value name="v0.35 grant fingerprint" value={admission.linkage.v035_grant_fingerprint.value} /><Value name="v0.35 status fingerprint" value={admission.linkage.v035_status_fingerprint.value} /><Value name="v0.35 request fingerprint" value={admission.linkage.v035_request_fingerprint.value} /><Value name="v0.35 confirmation fingerprint" value={admission.linkage.v035_confirmation_fingerprint.value} /><Value name="v0.35 operator fingerprint" value={admission.linkage.v035_operator_fingerprint.value} /><Value name="v0.34 review fingerprint" value={admission.linkage.v034_review_fingerprint.value} /><Value name="v0.20–v0.35 chain fingerprint" value={admission.linkage.chain_fingerprint.value} /><Value name="Admission linkage fingerprint" value={admission.linkage.linkage_fingerprint.value} /><Value name="Runner eligibility fingerprint" value={admission.runner_eligibility.eligibility_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={admission.idempotency_key_fingerprint.value} /><Value name="Audit evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit correlation ID" value={audit.correlation_id} /></dl>
            <details className="mt-3"><summary>Required v0.20–v0.34 evidence linkage inside v0.35 grant</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">{LINKAGE_KEYS.map((key) => <Value key={key} name={key} value={display(admission.linkage.permission_grant_linkage.readiness_linkage[key])} />)}</dl></details>
            <p className="mt-3 text-xs">Permanent idempotency reservation: true · permanent grant-subject reservation: true · raw idempotency key persisted: false · retry allowed: false · replay allowed: false.</p>
            <details className="mt-3"><summary>Fixed authority fields</summary><dl aria-label="Admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Execution start allowed", "Runner binding allowed", "Execution authorized", "Installation allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl></details>
        </details>
        <RunnerBindingPlans candidateId={admission.candidate_record_id} admission={result} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
