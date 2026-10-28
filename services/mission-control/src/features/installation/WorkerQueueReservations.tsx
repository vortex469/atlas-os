import { useEffect, useState } from "react";
import { listWorkerQueueReservations } from "../../api/workerQueueReservation";
import type { WorkerQueueReservationResultV1 } from "../../types/workerQueueReservation";
import { WorkerIntakeAdmissions } from "./WorkerIntakeAdmissions";

type QueueReservationBlocker =
    | "installation_capability_unsupported" | "evidence_not_found" | "ownership_mismatch"
    | "permission_scope_missing" | "linkage_mismatch" | "fingerprint_mismatch"
    | "evidence_stale" | "evidence_expired" | "worker_admission_not_active"
    | "worker_reference_ineligible" | "queue_intake_reference_ineligible"
    | "queue_item_reference_invalid" | "inherited_limits_mismatch"
    | "permanent_subject_reserved" | "live_enqueue_not_defined" | "dequeue_not_defined"
    | "worker_start_not_defined" | "execution_start_boundary_not_defined";

const BLOCKER_LABELS: Record<QueueReservationBlocker, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "Required evidence is missing",
    ownership_mismatch: "The evidence belongs to a different operator",
    permission_scope_missing: "Your account does not have permission to save this record",
    linkage_mismatch: "The evidence does not match this review",
    fingerprint_mismatch: "The saved evidence identity does not match",
    evidence_stale: "The earlier evidence is out of date",
    evidence_expired: "The earlier evidence has expired",
    worker_admission_not_active: "The earlier worker review record is no longer current",
    worker_reference_ineligible: "The worker reference cannot be used for this review",
    queue_intake_reference_ineligible: "The queue reference cannot be used for this review",
    queue_item_reference_invalid: "The queue item reference is invalid",
    inherited_limits_mismatch: "The safety limits do not match the earlier review",
    permanent_subject_reserved: "A record already exists for this review",
    live_enqueue_not_defined: "A safe way to add work to a live queue is not defined",
    dequeue_not_defined: "A safe way to take work from a queue is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
};

export function WorkerQueueReservations({ candidateId, stubId, homeAssistantBlocked }: { candidateId: string; stubId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<WorkerQueueReservationResultV1[] | null>(null); const [error, setError] = useState(false);
    useEffect(() => { let current = true; listWorkerQueueReservations(candidateId).then((value) => { if (current) setItems(value.items.filter((item) => item.reservation?.linkage.worker_admission_stub_id === stubId)); }).catch(() => { if (current) setError(true); }); return () => { current = false; }; }, [candidateId, stubId]);
    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Queue review">
        <h6 className="font-semibold">Queue review</h6>
        <p className="mt-2 text-sm">This record saves a queue reference for later review. It does not create or contact a live queue, add work, or start a worker.</p>
        <p className="mt-2 text-sm text-slate-400">No live queue is available in this review. Mission Control does not create queues or connect to them.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">Atlas cannot install Home Assistant, so it cannot be queued for installation.</p>}
        {items === null && !error && <p role="status" className="mt-3">Loading saved queue records…</p>}
        {error && <div role="alert"><p>Saved queue records could not be loaded.</p><p className="text-xs">Technical error details are hidden.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No queue record is saved. No work has been added to a queue or started.</p>}
        {items && <ol aria-label="Saved queue review records" className="mt-3 space-y-3">{items.map((result) => <Reservation key={result.reservation!.reservation_id} result={result} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Reservation({ result, homeAssistantBlocked }: { result: WorkerQueueReservationResultV1; homeAssistantBlocked: boolean }) {
    const record = result.reservation!; const status = result.status!; const intake = record.queue_intake_reference; const item = record.queue_item_reference; const link = record.linkage; const limits = record.inherited_limits; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status.lifecycle === "active" ? "Saved for later queue review" : "Expired queue review record"}</h6>
        <p className="mt-1">This record does not create a queue, add work, or start a worker.</p>
        <p className="mt-1">Saved <time dateTime={record.recorded_at}>{formatDateTime(record.recorded_at)}</time>; expires <time dateTime={record.valid_until}>{formatDateTime(record.valid_until)}</time>.</p>
        <h6 className="mt-3 font-medium">What still needs to be in place</h6>
        <ul aria-label="What still needs to be in place" className="mt-2 list-disc pl-5">{status.blockers.map((value) => <li key={value}>{BLOCKER_LABELS[value as QueueReservationBlocker] ?? "A queue or worker requirement is not met"}</li>)}</ul>
        <ul aria-label="Planned queue safety limits" className="mt-3 list-disc pl-5 text-slate-300">
            <li>No network access or live queue contact</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Queue and item details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value n="Operator" v={record.operator_id} /><Value n="Reservation record ID" v={record.reservation_id} /><Value n="Queue intake reference ID" v={intake.queue_intake_reference_id} /><Value n="Queue intake fingerprint" v={intake.reference_fingerprint.value} /><Value n="Queue kind code" v={intake.queue_kind} /><Value n="Queue eligibility code" v={intake.eligibility} /><Value n="Queue item reference ID" v={item.queue_item_reference_id} /><Value n="Queue item fingerprint" v={item.item_fingerprint.value} /><Value n="Item kind code" v={item.item_kind} /><Value n="Record fingerprint" v={record.record_fingerprint.value} /><Value n="Status fingerprint" v={status.status_fingerprint.value} /><Value n="Eligibility code" v={status.eligibility} /><Value n="Lifecycle code" v={status.lifecycle} /><Value n="Observed at" v={status.observed_at} /></dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Exact safety limits and earlier evidence</summary>
            <h6 className="mt-2 font-medium">Exact sandbox and resource limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value n="Sandbox profile" v={limits.sandbox.profile} /><Value n="Privilege, escalation, host namespaces, devices" v="false" /><Value n="Drop all capabilities" v="true" /><Value n="Seccomp and AppArmor required" v="true" /><Value n="CPU ceiling (millicores)" v={String(limits.resources.cpu_millis_max)} /><Value n="Memory ceiling (bytes)" v={String(limits.resources.memory_bytes_max)} /><Value n="PID ceiling" v={String(limits.resources.pids_max)} /><Value n="Wall-time ceiling (seconds)" v={String(limits.resources.wall_time_seconds_max)} /><Value n="Output ceiling (bytes)" v={String(limits.resources.output_bytes_max)} /><Value n="Network mode" v={limits.network.mode} /><Value n="Ingress, egress, DNS, image pull" v="false" /><Value n="Allowed endpoint fingerprints" v="none" /><Value n="Root filesystem read only" v="true" /><Value n="Host, repository, and guest mounts" v="false" /><Value n="Writable scope" v={limits.filesystem.writable_scope} /><Value n="Temporary workspace ceiling (bytes)" v={String(limits.filesystem.ephemeral_workspace_bytes_max)} /><Value n="Limits fingerprint" v={limits.limits_fingerprint.value} /></dl>
            <h6 className="mt-3 font-medium">Earlier evidence linked to this record</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value n="Earlier evidence chain fingerprint" v={link.v020_v037_chain_fingerprint.value} /><Value n="Readiness review fingerprint" v={link.readiness_review_fingerprint.value} /><Value n="Permission record fingerprint" v={link.permission_grant_fingerprint.value} /><Value n="Execution admission fingerprint" v={link.execution_admission_fingerprint.value} /><Value n="Runner plan fingerprint" v={link.runner_binding_plan_fingerprint.value} /><Value n="Worker review fingerprint" v={link.worker_admission_stub_fingerprint.value} /><Value n="Linkage fingerprint" v={link.linkage_fingerprint.value} /></dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Audit and authority details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value n="Audit event" v={audit.event} /><Value n="Audit outcome" v={audit.outcome} /><Value n="Audit fingerprint" v={audit.audit_fingerprint.value} /><Value n="Correlation fingerprint" v={audit.correlation_fingerprint.value} /></dl>
            <p className="mt-3 text-xs">This review record is reserved permanently. No work was consumed or released. It cannot be retried or replayed.</p>
            <dl aria-label="Queue reservation fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Live enqueue", "Dequeue", "Worker start", "Dispatch", "Execution", "Agent invocation", "Workflow start", "Provider mutation", "Repository mutation", "In-guest mutation", "Installation", "Deployment", "Rollback", "Retry", "Resend", "Replay bypass"].map((name) => <Value key={name} n={`${name} allowed`} v="false" />)}</dl>
        </details>
        <WorkerIntakeAdmissions candidateId={record.candidate_record_id} reservationId={record.reservation_id} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}
function Value({ n, v }: { n: string; v: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{n}</dt><dd className="mt-1 break-all text-slate-300">{v}</dd></div>; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
