import { useEffect, useState } from "react";

import { createInstallationExecutionAdmission, installationExecutionAdmissionIdempotencyKey, listInstallationExecutionAdmissions } from "../../api/installationExecutionAdmission";
import { LINKAGE_KEYS } from "../../api/installationReadinessReview";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ExecutionPermissionGrantResultV1 } from "../../types/executionPermissionGrant";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { InstallationExecutionAdmissionCreateV1, InstallationExecutionAdmissionResultV1 } from "../../types/installationExecutionAdmission";

const BLOCKER_LABELS: Record<string, string> = {
    runner_binding_not_defined: "Runner binding is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
    installation_capability_unsupported: "Installation capability unsupported",
    stale_evidence: "Stale evidence", expired_evidence: "Expired evidence",
    grant_not_active: "Permission grant is not active",
    grant_scope_mismatch: "Permission grant scope mismatch",
};

export function InstallationExecutionAdmissions({ candidateId, grants, homeAssistantBlocked }: { candidateId: string; grants: ExecutionPermissionGrantResultV1[]; homeAssistantBlocked: boolean }) {
    const session = useOperatorSession();
    const [admissions, setAdmissions] = useState<InstallationExecutionAdmissionResultV1[] | null>(null);
    const [error, setError] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    useEffect(() => {
        let current = true;
        listInstallationExecutionAdmissions(candidateId).then((value) => { if (current) setAdmissions(value.admissions); }).catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId]);

    const activeGrant = grants.find((item) => item.grant && item.status?.lifecycle === "active");
    const mayCreate = !homeAssistantBlocked && Boolean(activeGrant) && session.authenticated && session.principal?.permissions.includes("installation.execution.admission.record");
    const record = async () => {
        if (!session.csrfToken || !activeGrant?.grant || submitting) return;
        setSubmitting(true); setError(false);
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
            setAdmissions((current) => [result, ...(current ?? [])]); setConfirming(false);
        } catch { setError(true); }
        finally { setSubmitting(false); }
    };

    return <section aria-labelledby="execution-admissions-heading" className="mt-6 rounded border border-slate-700 p-4">
        <h2 id="execution-admissions-heading" className="font-semibold">Installation execution admission evidence</h2>
        <p className="mt-2 text-sm">This preserves a non-executing admission evidence record only. Admission gated is evidence status, not runner binding, execution start, installation, dispatch, retry or resend, Agent invocation, workflow or worker start, Docker, Podman, shell or process execution, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or mutation authority.</p>
        <p className="mt-2 text-sm">Core binds the authenticated operator, exact v0.20–v0.35 fingerprints, and the v0.35 permission grant. Freshness inherits at most 30 seconds. Expiry never refreshes evidence. Idempotency and grant subjects remain reserved permanently; raw keys are not persisted and replay is not allowed.</p>
        {admissions === null && !error && <p role="status" className="mt-4">Loading installation execution admission evidence…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>Installation execution admission evidence could not be recorded.</p><p className="text-xs text-slate-400">The error is redacted; no credential, provider payload, command, log, address, endpoint, or internal path is shown.</p></div>}
        {admissions?.length === 0 && <p role="status" className="mt-4">No installation execution admission evidence has been recorded.</p>}
        {admissions && admissions.length > 0 && <ol aria-label="Installation execution admissions" className="mt-4 space-y-4">{admissions.map((item) => <Admission key={item.admission!.admission_id} result={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-4 rounded border border-blue-400 px-3 py-2 text-sm">Review admission evidence statement</button>}
        {mayCreate && confirming && <div aria-label="Admission evidence confirmation" className="mt-4 rounded border border-amber-400/40 p-4">
            <p className="font-semibold">Step 2 of 2 — explicitly preserve evidence</p>
            <p className="mt-2 text-sm">This records admission evidence only. It does not select or invoke a runner and does not install or execute anything.</p>
            <p className="mt-2 text-xs">The record remains admission gated, non-authorizing, permanent, and unavailable for replay.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Record admission evidence</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-4 text-sm text-amber-200">Admission evidence creation remains blocked. A current v0.35 grant, authenticated owner, dedicated admission permission, and valid CSRF session are required. Home Assistant remains blocked, non-installable, and non-executable.</p>}
    </section>;
}

function Admission({ result }: { result: InstallationExecutionAdmissionResultV1 }) {
    const admission = result.admission!; const status = result.status!; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h3 className="font-semibold">{status.lifecycle === "active" ? "Active admission-gated evidence" : "Expired admission-gated evidence"}</h3>
        <p className="mt-1">Readiness: {admission.readiness}; lifecycle: {status.lifecycle}; disposition: {result.disposition}; record state: {admission.record_state}.</p>
        <p className="mt-1">Recorded {admission.recorded_at}; valid until {admission.valid_until}; observed {status.observed_at}. Expired evidence remains immutable and cannot regain freshness.</p>
        <ol aria-label="Ordered admission blockers" className="mt-2 list-decimal pl-5">{admission.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker] ?? blocker}</li>)}</ol>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2"><Value name="Authenticated operator" value={admission.operator_id} /><Value name="Admission ID" value={admission.admission_id} /><Value name="Admission fingerprint" value={admission.admission_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} /><Value name="v0.35 permission grant ID" value={admission.linkage.v035_grant_id} /><Value name="v0.35 grant fingerprint" value={admission.linkage.v035_grant_fingerprint.value} /><Value name="v0.35 status fingerprint" value={admission.linkage.v035_status_fingerprint.value} /><Value name="v0.35 request fingerprint" value={admission.linkage.v035_request_fingerprint.value} /><Value name="v0.35 confirmation fingerprint" value={admission.linkage.v035_confirmation_fingerprint.value} /><Value name="v0.35 operator fingerprint" value={admission.linkage.v035_operator_fingerprint.value} /><Value name="v0.34 review fingerprint" value={admission.linkage.v034_review_fingerprint.value} /><Value name="v0.20–v0.35 chain fingerprint" value={admission.linkage.chain_fingerprint.value} /><Value name="Admission linkage fingerprint" value={admission.linkage.linkage_fingerprint.value} /><Value name="Runner eligibility fingerprint" value={admission.runner_eligibility.eligibility_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={admission.idempotency_key_fingerprint.value} /><Value name="Audit evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit correlation ID" value={audit.correlation_id} /></dl>
        <details className="mt-3"><summary>Required v0.20–v0.34 evidence linkage inside v0.35 grant</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">{LINKAGE_KEYS.map((key) => <Value key={key} name={key} value={display(admission.linkage.permission_grant_linkage.readiness_linkage[key])} />)}</dl></details>
        <p className="mt-3 text-xs">Permanent idempotency reservation: true · permanent grant-subject reservation: true · raw idempotency key persisted: false · retry allowed: false · replay allowed: false.</p>
        <dl aria-label="Admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Execution start allowed", "Runner binding allowed", "Execution authorized", "Installation allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
