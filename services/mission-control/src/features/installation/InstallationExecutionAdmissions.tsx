import { useEffect, useState } from "react";

import { createInstallationExecutionAdmission, installationExecutionAdmissionIdempotencyKey, listInstallationExecutionAdmissions } from "../../api/installationExecutionAdmission";
import { LINKAGE_KEYS } from "../../api/installationReadinessReview";
import { useOperatorSession } from "../../hooks/operatorSessionContext";
import type { ExecutionPermissionGrantResultV1 } from "../../types/executionPermissionGrant";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { AdmissionBlockerV1, InstallationExecutionAdmissionCreateV1, InstallationExecutionAdmissionResultV1 } from "../../types/installationExecutionAdmission";
import { RunnerBindingPlans } from "./RunnerBindingPlans";

const BLOCKER_LABELS: Record<AdmissionBlockerV1, string> = {
    missing_evidence: "Some required evidence is missing",
    ownership_mismatch: "The evidence belongs to a different operator",
    linkage_mismatch: "The evidence does not match this review",
    fingerprint_mismatch: "The saved evidence identity does not match",
    invalid_evidence: "The saved evidence could not be checked",
    stale_evidence: "The saved evidence is out of date",
    expired_evidence: "The saved evidence has expired",
    grant_not_active: "The earlier permission record is no longer current",
    grant_scope_mismatch: "The earlier permission record does not match this review",
    grant_unavailable: "The earlier permission record is unavailable",
    permission_denied: "Your account does not have permission to save this record",
    subject_reserved: "A record already exists for this review",
    installation_capability_unsupported: "Atlas cannot install this application",
    runner_binding_not_defined: "No runner is selected",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
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
            setAdmissions((current) => [
                result,
                ...(current ?? []).filter((item) => item.admission?.admission_id !== result.admission?.admission_id),
            ]);
            setConfirming(false);
        } catch { setError(true); }
        finally { setSubmitting(false); }
    };

    return <section aria-labelledby="execution-admissions-heading" className="mt-6 rounded border border-slate-700 p-4">
        <h2 id="execution-admissions-heading" className="font-semibold">Save a request for later runner review</h2>
        <p className="mt-2 text-sm">This saves a request for an installation runner to be considered later. It does not choose or contact a runner, authorize installation, or start work.</p>
        <p className="mt-2 text-sm text-slate-400">The record expires within 30 seconds, or sooner if the earlier permission record expires. It cannot be renewed or submitted again.</p>
        {admissions === null && !error && <p role="status" className="mt-4">Loading saved runner review records…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>The saved runner review records are unavailable or could not be saved.</p><p className="text-xs text-slate-400">The error is hidden. No credentials, commands, logs, addresses, or internal paths are shown.</p></div>}
        {admissions?.length === 0 && <p role="status" className="mt-4">No runner review records saved yet.</p>}
        {admissions && admissions.length > 0 && <ol aria-label="Runner review records" className="mt-4 space-y-4">{admissions.map((item) => <Admission key={item.admission!.admission_id} result={item} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
        {mayCreate && !confirming && <button type="button" aria-label="Review runner review record" onClick={() => setConfirming(true)} className="mt-4 rounded border border-blue-400 px-3 py-2 text-sm">Review this record</button>}
        {mayCreate && confirming && <div aria-label="Admission evidence confirmation" className="mt-4 rounded border border-amber-400/40 p-4">
            <p className="font-semibold">Save this request for later review?</p>
            <p className="mt-2 text-sm">Saving records your request for an installation runner to be considered later. It does not choose or contact a runner, authorize installation, or start work.</p>
            <details className="mt-3 text-xs text-slate-400"><summary className="cursor-pointer">Check the permission record</summary>
                <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                    <Value name="Candidate record ID" value={candidateId} />
                    <Value name="Permission record ID" value={activeGrant?.grant?.grant_id ?? "Not available"} />
                    <Value name="Permission record fingerprint" value={activeGrant?.grant?.grant_fingerprint.value ?? "Not available"} />
                    <Value name="Permission record expires" value={activeGrant?.grant?.valid_until ?? "Not available"} />
                </dl>
            </details>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Save for later review</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
            {submitting && <p role="status" className="mt-2 text-sm">Saving review record…</p>}
        </div>}
        {!mayCreate && <p className="mt-4 text-sm text-amber-200">Saving is unavailable. It requires a current permission record, an authenticated operator with the dedicated permission, and a valid session.{homeAssistantBlocked && " Atlas cannot install Home Assistant."}</p>}
    </section>;
}

function Admission({ result, homeAssistantBlocked }: { result: InstallationExecutionAdmissionResultV1; homeAssistantBlocked: boolean }) {
    const admission = result.admission!; const status = result.status!; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h3 className="font-semibold">{status.lifecycle === "active" ? "Saved for later review" : "Expired review request"}</h3>
        <p className="mt-1">This record does not choose or contact a runner, authorize installation, or start work.</p>
        <p className="mt-1">Saved {admission.recorded_at}; expires {admission.valid_until}.</p>
        <h4 className="mt-3 text-sm font-medium">What still needs to be in place</h4>
        <ul aria-label="What still needs to be in place" className="mt-2 list-disc pl-5">{admission.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker]}</li>)}</ul>
        <details className="mt-3 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Record identity and technical status</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Authenticated operator" value={admission.operator_id} />
                <Value name="Candidate record ID" value={admission.candidate_record_id} />
                <Value name="Admission record ID" value={admission.admission_id} />
                <Value name="Admission fingerprint" value={admission.admission_fingerprint.value} />
                <Value name="Status fingerprint" value={status.status_fingerprint.value} />
                <Value name="Readiness code" value={admission.readiness} />
                <Value name="Lifecycle code" value={status.lifecycle} />
                <Value name="Disposition code" value={result.disposition} />
                <Value name="Record state code" value={admission.record_state} />
                <Value name="Observed at" value={status.observed_at} />
                <Value name="Permission record ID" value={admission.linkage.v035_grant_id} />
                <Value name="Permission record fingerprint" value={admission.linkage.v035_grant_fingerprint.value} />
                <Value name="Permission status fingerprint" value={admission.linkage.v035_status_fingerprint.value} />
                <Value name="Permission request fingerprint" value={admission.linkage.v035_request_fingerprint.value} />
                <Value name="Permission confirmation fingerprint" value={admission.linkage.v035_confirmation_fingerprint.value} />
                <Value name="Permission operator fingerprint" value={admission.linkage.v035_operator_fingerprint.value} />
                <Value name="Earlier review fingerprint" value={admission.linkage.v034_review_fingerprint.value} />
                <Value name="Evidence chain fingerprint" value={admission.linkage.chain_fingerprint.value} />
                <Value name="Linkage fingerprint" value={admission.linkage.linkage_fingerprint.value} />
                <Value name="Runner eligibility fingerprint" value={admission.runner_eligibility.eligibility_fingerprint.value} />
                <Value name="Request fingerprint" value={admission.request_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={admission.idempotency_key_fingerprint.value} />
                <Value name="Audit evidence fingerprint" value={audit.evidence_fingerprint.value} />
                <Value name="Audit outcome code" value={audit.outcome} />
                <Value name="Audit correlation ID" value={audit.correlation_id} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Earlier evidence linked to this record</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">{LINKAGE_KEYS.map((key) => <Value key={key} name={key} value={display(admission.linkage.permission_grant_linkage.readiness_linkage[key])} />)}</dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Audit and authority details</summary>
            <p className="mt-2 text-xs">Idempotency and permission-record use are reserved permanently. The raw key is not saved, and this record cannot be retried or replayed.</p>
            <dl aria-label="Admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Execution start allowed", "Runner binding allowed", "Execution authorized", "Installation allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        </details>
        <RunnerBindingPlans candidateId={admission.candidate_record_id} admission={result} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
