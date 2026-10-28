import { useEffect, useState } from "react";

import { listWorkerBindingActivationPreflights } from "../../api/workerBindingActivationPreflight";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { WorkerBindingActivationPreflightV1 } from "../../types/workerBindingActivationPreflight";
import { WorkerBindingActivationEvidences } from "./WorkerBindingActivationEvidences";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

export function WorkerBindingActivationPreflights({ candidateId, bindingId }: { candidateId: string; bindingId: string }) {
    const [items, setItems] = useState<WorkerBindingActivationPreflightV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listWorkerBindingActivationPreflights(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.one_shot_dequeue_worker_binding.binding_id === bindingId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, bindingId]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Worker binding activation preflight evidence">
        <h6 className="font-semibold">Worker activation preflight</h6>
        <p className="mt-2 text-sm">This screen shows a preflight record. It is read-only and cannot activate or contact a worker, or start work.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading preflight records...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Preflight records are unavailable.</p><p className="text-xs text-slate-400">Technical error details are hidden.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No preflight is recorded for this binding. Worker activation remains blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Worker binding activation preflights">{items.map((item) => <Preflight key={item.preflight_id} item={item} />)}</ol>}
    </section>;
}

function Preflight({ item }: { item: WorkerBindingActivationPreflightV1 }) {
    const binding = item.one_shot_dequeue_worker_binding;
    const worker = binding.worker_intake_admission.worker_identity;
    const intake = binding.worker_intake_admission.worker_intake_reference;
    const limits = binding.worker_intake_admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Preflight recorded</p>
        <BlockerSummary blockers={item.blockers} />
        <p className="mt-2">This record does not contact a store or runtime, take queue work, or start a worker.</p>
        <p className="mt-1">Recorded {formatDateTime(item.recorded_at)} · Expires {formatDateTime(item.valid_until)}. Expiry does not trigger an action.</p>
        <details className="mt-3">
            <summary>Advanced details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Preflight ID" value={item.preflight_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Eligibility" value={item.eligibility} />
                <Value name="Lifecycle" value={item.lifecycle} />
                <Value name="Preflight state" value={item.preflight_state} />
                <Value name="Preflight fingerprint" value={item.preflight_record_fingerprint.value} />
                <Value name="Subject fingerprint" value={item.subject_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint.value} />
                <Value name="v0.46 binding" value={binding.binding_id} />
                <Value name="v0.46 binding fingerprint" value={binding.binding_record_fingerprint.value} />
                <Value name="v0.46 binding status fingerprint" value={item.one_shot_dequeue_worker_binding_status.status_fingerprint.value} />
                <Value name="v0.45 one-shot dequeue" value={binding.one_shot_controlled_dequeue.dequeue_id} />
                <Value name="v0.40 worker intake admission" value={binding.worker_intake_admission.admission_id} />
                <Value name="Binding subject fingerprint" value={item.binding_subject_fingerprint.value} />
                <Value name="Worker subject fingerprint" value={item.worker_subject_fingerprint.value} />
                <Value name="Worker identity ID" value={worker.worker_identity_id} />
                <Value name="Worker kind" value={worker.worker_kind} />
                <Value name="Worker trust domain" value={worker.trust_domain} />
                <Value name="Worker eligibility" value={worker.eligibility} />
                <Value name="Worker capability fingerprint" value={worker.capability_profile_fingerprint.value} />
                <Value name="Worker intake reference" value={intake.worker_intake_reference_id} />
                <Value name="Worker intake protocol" value={intake.intake_protocol} />
                <Value name="Queue item reference fingerprint" value={item.queue_item_reference_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Blockers</h6>
            <ol aria-label="Ordered worker binding activation preflight blockers" className="mt-2 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{workerBindingActivationBlockerLabel(value)} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
            <h6 className="mt-3 font-semibold">Inherited sandbox, resource, network, and filesystem limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privileged / escalation / host namespaces / devices" value="false" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Inherited limits fingerprint" value={item.inherited_limits_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">Permanent preflight subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · credential material present: false · endpoint material present: false · command material present: false · payload material present: false.</p>
            <dl aria-label="Worker binding activation preflight fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Binding activation allowed", "Caller-supplied credentials allowed", "Caller-supplied endpoint allowed", "Caller-supplied command allowed", "Caller-supplied payload allowed", "Store contact allowed", "Runtime contact allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue acknowledgement allowed", "Queue consume allowed", "Queue mutation allowed", "Worker store contact allowed", "Worker runtime contact allowed", "Worker contact allowed", "Worker start allowed", "Worker invocation allowed", "Agent invocation allowed", "Execution authorization allowed", "Execution start allowed", "Process execution allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Workflow start allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Artifact publication allowed", "Tag push allowed", "Release publication allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <WorkerBindingActivationEvidences candidateId={item.candidate_record_id} preflightId={item.preflight_id} />
    </li>;
}

function BlockerSummary({ blockers }: { blockers: WorkerBindingActivationPreflightV1["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-1">No blockers are listed. This record still does not activate the worker.</p>;
    return <div className="mt-1 rounded border border-amber-500/40 p-2" aria-label="Worker activation status">
        <p className="font-semibold">Worker activation is blocked</p>
        <p>{blockers.length} {blockers.length === 1 ? "requirement remains" : "requirements remain"} unavailable.</p>
        <details className="mt-1">
            <summary>Show what needs to be in place</summary>
            <ul aria-label="Worker activation blockers" className="mt-2 list-disc pl-5">
                {blockers.map((blocker) => <li key={blocker}>{workerBindingActivationBlockerLabel(blocker)}</li>)}
            </ul>
        </details>
    </div>;
}

function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
