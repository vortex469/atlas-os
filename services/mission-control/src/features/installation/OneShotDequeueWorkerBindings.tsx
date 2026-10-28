import { useEffect, useState } from "react";

import { listOneShotDequeueWorkerBindings } from "../../api/oneShotDequeueWorkerBinding";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotDequeueWorkerBindingBlockerV1, OneShotDequeueWorkerBindingV1 } from "../../types/oneShotDequeueWorkerBinding";
import { WorkerBindingActivationPreflights } from "./WorkerBindingActivationPreflights";

const BLOCKERS: Record<OneShotDequeueWorkerBindingBlockerV1, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "An earlier review is missing",
    ownership_mismatch: "An earlier review belongs to a different operator",
    permission_scope_missing: "Your account does not have permission for this review",
    v045_dequeue_not_active: "The queue reference removal is no longer current",
    v045_dequeue_not_recorded: "The queue reference removal was not saved",
    v045_dequeue_not_successful: "The exact queue reference was not removed successfully",
    v040_worker_intake_not_active: "The worker intake review is no longer current",
    v040_worker_intake_not_recorded: "The worker intake review was not saved",
    linkage_mismatch: "The earlier reviews do not match each other",
    worker_subject_mismatch: "The worker reference does not match this review",
    queue_item_reference_mismatch: "The queue reference does not match this review",
    fingerprint_mismatch: "A saved evidence identity does not match",
    inherited_limits_mismatch: "The safety limits do not match the earlier review",
    evidence_stale: "An earlier review is out of date",
    evidence_expired: "An earlier review has expired",
    ambiguous_state: "Atlas could not confirm the result",
    caller_supplied_credential: "Credentials cannot be supplied by the caller",
    caller_supplied_endpoint: "An endpoint cannot be supplied by the caller",
    caller_supplied_command: "A command cannot be supplied by the caller",
    unsupported_authority: "The queue reference does not have the required safety limits",
    store_contact_not_defined: "A safe way to contact the store is not defined",
    runtime_contact_not_defined: "A safe way to contact the runtime is not defined",
    worker_start_not_defined: "A safe way to start a worker is not defined",
    execution_start_boundary_not_defined: "A safe way to start installation is not defined",
    reservation_before_effect_failed: "Saving was blocked before a binding was created",
    permanent_subject_reserved: "A binding is already saved for this queue reference",
    idempotency_conflict: "A conflicting save request was received",
    append_indeterminate: "Atlas could not confirm whether the binding was saved",
};

export function OneShotDequeueWorkerBindings({ candidateId, dequeueId }: { candidateId: string; dequeueId: string }) {
    const [items, setItems] = useState<OneShotDequeueWorkerBindingV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listOneShotDequeueWorkerBindings(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.one_shot_controlled_dequeue.dequeue_id === dequeueId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, dequeueId]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Worker readiness review">
        <h6 className="font-semibold">Worker readiness review</h6>
        <p className="mt-2 text-sm">This record links the saved queue reference to a possible future worker setup. It does not contact a store or runtime or start a worker.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading worker readiness reviews…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Worker readiness reviews could not be loaded.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No worker readiness review is saved. A worker has not been started.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Saved worker readiness reviews">{items.map((item) => <Binding key={item.binding_id} item={item} />)}</ol>}
    </section>;
}

function Binding({ item }: { item: OneShotDequeueWorkerBindingV1 }) {
    const worker = item.worker_intake_admission.worker_identity;
    const intake = item.worker_intake_admission.worker_intake_reference;
    const limits = item.worker_intake_admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Worker readiness review saved</h6>
        <p className="mt-1">This review does not contact a store or runtime or start a worker.</p>
        <p className="mt-1">Saved {formatDateTime(item.recorded_at)} · Expires {formatDateTime(item.valid_until)}.</p>
        <h6 className="mt-3 font-medium">Why a worker cannot start</h6>
        <ul aria-label="Why a worker cannot start" className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}>{BLOCKERS[value]}</li>)}</ul>
        <h6 className="mt-3 font-medium">Limits recorded for a future worker</h6>
        <ul aria-label="Limits recorded for a future worker" className="mt-2 list-disc pl-5 text-slate-300">
            <li>No network access</li>
            <li>No access to host, repository, or guest files</li>
            <li>No elevated privileges; changes stay in a temporary workspace</li>
            <li>Limits: {formatCpu(limits.resources.cpu_millis_max)}, {formatMiB(limits.resources.memory_bytes_max)} memory, {limits.resources.pids_max} processes, {formatDuration(limits.resources.wall_time_seconds_max)}, {formatMiB(limits.resources.output_bytes_max)} output, and {formatMiB(limits.filesystem.ephemeral_workspace_bytes_max)} temporary workspace</li>
        </ul>
        <details className="mt-3 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Worker and queue details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Binding ID" value={item.binding_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Eligibility" value={item.eligibility} />
                <Value name="Lifecycle" value={item.lifecycle} />
                <Value name="Binding state" value={item.binding_state} />
                <Value name="Binding fingerprint" value={item.binding_record_fingerprint.value} />
                <Value name="Subject fingerprint" value={item.subject_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint.value} />
                <Value name="v0.45 one-shot dequeue" value={item.one_shot_controlled_dequeue.dequeue_id} />
                <Value name="v0.45 dequeue fingerprint" value={item.one_shot_controlled_dequeue.dequeue_record_fingerprint.value} />
                <Value name="v0.45 dequeue status fingerprint" value={item.one_shot_controlled_dequeue_status.status_fingerprint.value} />
                <Value name="v0.40 worker intake admission" value={item.worker_intake_admission.admission_id} />
                <Value name="v0.40 worker intake fingerprint" value={item.worker_intake_admission.record_fingerprint.value} />
                <Value name="v0.40 worker intake status fingerprint" value={item.worker_intake_admission_status.status_fingerprint.value} />
                <Value name="Worker identity ID" value={worker.worker_identity_id} />
                <Value name="Worker kind" value={worker.worker_kind} />
                <Value name="Worker trust domain" value={worker.trust_domain} />
                <Value name="Worker eligibility" value={worker.eligibility} />
                <Value name="Worker identity fingerprint" value={item.worker_subject_fingerprint.value} />
                <Value name="Worker capability fingerprint" value={worker.capability_profile_fingerprint.value} />
                <Value name="Worker intake reference ID" value={intake.worker_intake_reference_id} />
                <Value name="Worker intake protocol code" value={intake.intake_protocol} />
                <Value name="Queue item reference fingerprint" value={item.queue_item_reference_fingerprint.value} />
                <Value name="Eligibility code" value={item.eligibility} />
                <Value name="Lifecycle code" value={item.lifecycle} />
                <Value name="Binding state code" value={item.binding_state} />
            </dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3">
            <summary className="cursor-pointer">Exact safety and authority details</summary>
            <h6 className="mt-2 font-medium">Inherited limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privilege, escalation, host namespaces, devices" value="false" />
                <Value name="Drop all capabilities" value="true" />
                <Value name="Seccomp and AppArmor required" value="true" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
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
                <Value name="Inherited limits fingerprint" value={item.inherited_limits_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">This binding cannot be replayed. The raw idempotency key, credentials, endpoints, and commands are not saved.</p>
            <dl aria-label="One-shot dequeue worker binding fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Caller-supplied credentials allowed", "Caller-supplied endpoint allowed", "Caller-supplied command allowed", "Store contact allowed", "Runtime contact allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue acknowledgement allowed", "Queue mutation allowed", "Worker contact allowed", "Worker start allowed", "Agent invocation allowed", "Execution start allowed", "Process execution allowed", "Dispatch allowed", "Retry allowed", "Workflow start allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <WorkerBindingActivationPreflights candidateId={item.candidate_record_id} bindingId={item.binding_id} />
    </li>;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
function formatMiB(bytes: number) { return `${bytes / (1024 * 1024)} MiB`; }
function formatCpu(millis: number) { const cores = millis / 1000; return `${cores} ${cores === 1 ? "CPU core" : "CPU cores"}`; }
function formatDuration(seconds: number) { const minutes = seconds / 60; return Number.isInteger(minutes) ? `${minutes} ${minutes === 1 ? "minute" : "minutes"}` : `${seconds} seconds`; }
