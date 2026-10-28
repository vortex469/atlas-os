import { useEffect, useState } from "react";

import { listWorkerIntakeAdmissions } from "../../api/workerIntakeAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { WorkerIntakeAdmissionV1 } from "../../types/workerIntakeAdmission";
import { LiveEnqueueAdmissions } from "./LiveEnqueueAdmissions";

type WorkerIntakeBlocker =
    | "installation_capability_unsupported" | "evidence_not_found" | "ownership_mismatch"
    | "permission_scope_missing" | "linkage_mismatch" | "fingerprint_mismatch"
    | "evidence_stale" | "evidence_expired" | "worker_queue_reservation_not_active"
    | "worker_identity_ineligible" | "worker_intake_reference_ineligible"
    | "queue_reservation_binding_mismatch" | "inherited_limits_mismatch"
    | "permanent_subject_reserved" | "live_enqueue_not_defined" | "dequeue_not_defined"
    | "worker_start_not_defined" | "execution_start_boundary_not_defined";

const BLOCKERS: Record<WorkerIntakeBlocker, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "Required evidence is missing",
    ownership_mismatch: "The evidence belongs to a different operator",
    permission_scope_missing: "Your account does not have permission to save this record",
    linkage_mismatch: "The evidence does not match this review",
    fingerprint_mismatch: "The saved evidence identity does not match",
    evidence_stale: "The earlier evidence is out of date",
    evidence_expired: "The earlier evidence has expired",
    worker_queue_reservation_not_active: "The earlier queue record is no longer current",
    worker_identity_ineligible: "The worker reference cannot be used for this review",
    worker_intake_reference_ineligible: "The intake reference cannot be used for this review",
    queue_reservation_binding_mismatch: "The queue record does not match this review",
    inherited_limits_mismatch: "The safety limits do not match the earlier review",
    permanent_subject_reserved: "A record already exists for this review",
    live_enqueue_not_defined: "A safe way to add work to a queue is not defined",
    dequeue_not_defined: "A safe way to take work from a queue is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
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

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Worker intake review">
        <h6 className="font-semibold">Worker intake review</h6>
        <p className="mt-2 text-sm">This saved record checks the worker and intake references for a later review. It does not contact a worker, send work to a queue, or start anything.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">Atlas cannot install Home Assistant, so it cannot be prepared for a worker.</p>}
        {items === null && !error && <p role="status" className="mt-3">Loading saved worker intake reviews…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Saved worker intake reviews could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No worker intake review is saved. No work has been sent to a queue or started.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Saved worker intake reviews">{items.map((item) => <Admission key={item.admission_id} admission={item} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Admission({ admission, homeAssistantBlocked }: { admission: WorkerIntakeAdmissionV1; homeAssistantBlocked: boolean }) {
    const status = isExpired(admission.valid_until) ? "Expired worker intake review" : "Saved worker intake review";
    const identity = admission.worker_identity;
    const intake = admission.worker_intake_reference;
    const decision = admission.admission_decision;
    const limits = admission.inherited_limits;
    const link = admission.linkage;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status}</h6>
        <p className="mt-1">This check does not mean a worker is available or that work can start.</p>
        <p className="mt-1">Saved {formatDateTime(admission.recorded_at)} · Expires {formatDateTime(admission.valid_until)}.</p>
        <h6 className="mt-3 font-medium">Why work cannot start</h6>
        <ul aria-label="Why work cannot start" className="mt-2 list-disc pl-5">{admission.blockers.map((value) => <li key={value}>{BLOCKERS[value as WorkerIntakeBlocker] ?? "A worker or queue requirement is not met"}</li>)}</ul>
        <h6 className="mt-3 font-medium">Safety limits recorded for a future worker</h6>
        <ul aria-label="Safety limits recorded for a future worker" className="mt-2 list-disc pl-5 text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Worker and intake details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Admission ID" value={admission.admission_id} />
                <Value name="Authenticated operator" value={admission.operator_id} />
                <Value name="Record fingerprint" value={admission.record_fingerprint.value} />
                <Value name="Subject fingerprint" value={admission.subject_fingerprint.value} />
                <Value name="Eligibility code" value={admission.eligibility} />
                <Value name="Lifecycle code" value={admission.lifecycle} />
                <Value name="Worker identity ID" value={identity.worker_identity_id} />
                <Value name="Worker eligibility code" value={identity.eligibility} />
                <Value name="Worker kind code" value={identity.worker_kind} />
                <Value name="Intake reference ID" value={intake.worker_intake_reference_id} />
                <Value name="Intake eligibility code" value={intake.eligibility} />
                <Value name="Intake protocol code" value={intake.intake_protocol} />
                <Value name="Decision code" value={decision.decision} />
                <Value name="Decision evaluated at" value={decision.evaluated_at} />
                <Value name="Decision fingerprint" value={decision.decision_fingerprint.value} />
                <Value name="Request fingerprint" value={admission.request_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={admission.idempotency_key_fingerprint.value} />
                <Value name="Worker identity fingerprint" value={identity.worker_identity_fingerprint.value} />
                <Value name="Worker capability fingerprint" value={identity.capability_profile_fingerprint.value} />
                <Value name="Worker intake fingerprint" value={intake.intake_reference_fingerprint.value} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Exact safety limits and earlier evidence</summary>
            <h6 className="mt-2 font-medium">Exact sandbox and resource limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privilege, escalation, host namespaces, devices" value="false" />
                <Value name="Drop all capabilities" value="true" />
                <Value name="Seccomp and AppArmor required" value="true" />
                <Value name="CPU ceiling (millicores)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Wall-time ceiling (seconds)" value={String(limits.resources.wall_time_seconds_max)} />
                <Value name="Output ceiling (bytes)" value={String(limits.resources.output_bytes_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Ingress, egress, DNS, image pull" value="false" />
                <Value name="Root filesystem read only" value="true" />
                <Value name="Host, repository, and guest mounts" value="false" />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Temporary workspace ceiling (bytes)" value={String(limits.filesystem.ephemeral_workspace_bytes_max)} />
                <Value name="Inherited limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-medium">Earlier evidence linked to this record</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Earlier evidence chain fingerprint" value={link.v020_v038_chain_fingerprint.value} />
                <Value name="Readiness review fingerprint" value={link.readiness_review_fingerprint.value} />
                <Value name="Permission record fingerprint" value={link.permission_grant_fingerprint.value} />
                <Value name="Execution admission fingerprint" value={link.execution_admission_fingerprint.value} />
                <Value name="Runner plan fingerprint" value={link.runner_binding_plan_fingerprint.value} />
                <Value name="Worker review fingerprint" value={link.worker_admission_stub_fingerprint.value} />
                <Value name="Queue reservation ID" value={link.queue_reservation_id} />
                <Value name="Queue reservation fingerprint" value={link.queue_reservation_fingerprint.value} />
                <Value name="Queue reservation status fingerprint" value={link.queue_reservation_status_fingerprint.value} />
                <Value name="Linkage fingerprint" value={link.linkage_fingerprint.value} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Record and authority details</summary>
            <p className="mt-2 text-xs">This record cannot be retried or replayed. The raw idempotency key is not saved.</p>
            <dl aria-label="Worker intake admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {[
                    "Live enqueue allowed", "Dequeue allowed", "Queue polling allowed", "Worker contact allowed", "Worker start allowed", "Execution start allowed", "Runner binding allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed",
                ].map((name) => <Value key={name} name={name} value="false" />)}
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
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
