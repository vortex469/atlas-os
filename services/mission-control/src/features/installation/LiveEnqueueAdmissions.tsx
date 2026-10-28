import { useEffect, useState } from "react";

import { listLiveEnqueueAdmissions } from "../../api/liveEnqueueAdmission";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { LiveEnqueueAdmissionV1, LiveEnqueueBlockerV1 } from "../../types/liveEnqueueAdmission";
import { OneShotLiveEnqueues } from "./OneShotLiveEnqueues";

const BLOCKERS: Record<LiveEnqueueBlockerV1, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "An earlier review is missing",
    ownership_mismatch: "An earlier review belongs to a different operator",
    permission_scope_missing: "Your account does not have permission for this review",
    linkage_mismatch: "The earlier reviews do not match each other",
    fingerprint_mismatch: "A saved evidence identity does not match",
    evidence_stale: "An earlier review is out of date",
    evidence_expired: "An earlier review has expired",
    worker_intake_admission_not_active: "The worker intake review is no longer current",
    queue_reservation_not_active: "The queue reservation is no longer current",
    queue_item_reference_invalid: "The queue item reference is missing or invalid",
    worker_identity_ineligible: "The worker reference cannot be used for this review",
    worker_intake_reference_ineligible: "The intake reference cannot be used for this review",
    inherited_limits_mismatch: "The safety limits do not match the earlier review",
    permanent_subject_reserved: "A review is already saved for this queue item",
    enqueue_operation_not_defined: "A safe way to add work to a queue is not defined",
    dequeue_not_defined: "A safe way to take work from a queue is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
};

export function LiveEnqueueAdmissions({ candidateId, workerIntakeAdmissionId, homeAssistantBlocked }: { candidateId: string; workerIntakeAdmissionId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<LiveEnqueueAdmissionV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listLiveEnqueueAdmissions(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.linkage.worker_intake_admission_id === workerIntakeAdmissionId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, workerIntakeAdmissionId]);

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Queue handoff review">
        <h6 className="font-semibold">Queue handoff review</h6>
        <p className="mt-2 text-sm">This saved check reviews the evidence needed before work could be added to a queue. It does not create or send work, contact a worker, or start anything.</p>
        <p className="mt-2 text-sm">Atlas has not defined a safe queue handoff or worker start for this path. This review cannot make that capability available.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">Atlas cannot install Home Assistant, so it cannot be prepared for a worker.</p>}
        {items === null && !error && <p role="status" className="mt-3">Loading saved queue handoff reviews…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Saved queue handoff reviews could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No queue handoff review is saved. No work has been added to a queue or started.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Saved queue handoff reviews">{items.map((item) => <Admission key={item.admission_id} admission={item} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Admission({ admission, homeAssistantBlocked }: { admission: LiveEnqueueAdmissionV1; homeAssistantBlocked: boolean }) {
    const status = isExpired(admission.valid_until) ? "Expired queue handoff review" : "Saved queue handoff review";
    const decision = admission.admission_decision;
    const link = admission.linkage;
    const limits = admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">{status}</h6>
        <p className="mt-1">This saved check does not mean work can be added to a queue.</p>
        <p className="mt-1">Saved {formatDateTime(admission.recorded_at)} · Expires {formatDateTime(admission.valid_until)}.</p>
        <h6 className="mt-3 font-medium">Why work cannot be added</h6>
        <ul aria-label="Why work cannot be added" className="mt-2 list-disc pl-5">{admission.blockers.map((value) => <li key={value}>{BLOCKERS[value]}</li>)}</ul>
        <h6 className="mt-3 font-medium">Safety limits recorded for a future worker</h6>
        <ul aria-label="Safety limits recorded for a future worker" className="mt-2 list-disc pl-5 text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Queue and worker details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Admission ID" value={admission.admission_id} />
                <Value name="Authenticated operator" value={admission.operator_id} />
                <Value name="Record fingerprint" value={admission.record_fingerprint.value} />
                <Value name="Subject fingerprint" value={admission.subject_fingerprint.value} />
                <Value name="Request fingerprint" value={admission.request_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={admission.idempotency_key_fingerprint.value} />
                <Value name="Worker intake admission fingerprint" value={link.worker_intake_admission_fingerprint.value} />
                <Value name="Worker intake status fingerprint" value={link.worker_intake_admission_status_fingerprint.value} />
                <Value name="Queue reservation fingerprint" value={link.queue_reservation_fingerprint.value} />
                <Value name="Queue reservation status fingerprint" value={link.queue_reservation_status_fingerprint.value} />
                <Value name="Queue item fingerprint" value={link.queue_item_reference_fingerprint.value} />
                <Value name="Worker identity fingerprint" value={link.worker_identity_fingerprint.value} />
                <Value name="Worker intake reference fingerprint" value={link.worker_intake_reference_fingerprint.value} />
                <Value name="v0.20-v0.39 chain fingerprint" value={link.v020_v039_chain_fingerprint.value} />
                <Value name="Decision fingerprint" value={decision.decision_fingerprint.value} />
                <Value name="Linkage fingerprint" value={link.linkage_fingerprint.value} />
                <Value name="Eligibility code" value={admission.eligibility} />
                <Value name="Lifecycle code" value={admission.lifecycle} />
                <Value name="Decision code" value={decision.decision} />
                <Value name="Decision evaluated at" value={decision.evaluated_at} />
                <Value name="Worker intake admission ID" value={link.worker_intake_admission_id} />
                <Value name="Queue reservation ID" value={link.queue_reservation_id} />
                <Value name="Queue item reference ID" value={link.queue_item_reference_id} />
                <Value name="Worker identity ID" value={link.worker_identity_id} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Exact safety limits and saved evidence</summary>
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
            <h6 className="mt-3 font-medium">Earlier evidence linked to this review</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Readiness review fingerprint" value={link.readiness_review_fingerprint.value} />
                <Value name="Permission record fingerprint" value={link.permission_grant_fingerprint.value} />
                <Value name="Execution admission fingerprint" value={link.execution_admission_fingerprint.value} />
                <Value name="Runner plan fingerprint" value={link.runner_binding_plan_fingerprint.value} />
                <Value name="Worker review fingerprint" value={link.worker_admission_stub_fingerprint.value} />
                <Value name="Queue reservation status fingerprint" value={link.queue_reservation_status_fingerprint.value} />
                <Value name="Worker intake status fingerprint" value={link.worker_intake_admission_status_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">This review cannot be retried or replayed. The raw idempotency key is not saved.</p>
            <p className="mt-2 text-xs">Audit facts are server-owned and fingerprint-bound. Technical identifiers are shown here for review.</p>
            <dl aria-label="Live enqueue admission fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Live enqueue allowed", "Enqueue operation defined", "Queue item payload defined", "Payload constructed", "Payload serialized", "Queue publish allowed", "Queue send allowed", "Dequeue allowed", "Queue polling allowed", "Queue claim allowed", "Queue ack allowed", "Worker contact allowed", "Worker authentication allowed", "Worker binding allowed", "Worker start allowed", "Execution start allowed", "Runner binding allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Docker execution allowed", "Podman execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <OneShotLiveEnqueues candidateId={admission.candidate_record_id} liveEnqueueAdmissionId={admission.admission_id} homeAssistantBlocked={homeAssistantBlocked} />
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
