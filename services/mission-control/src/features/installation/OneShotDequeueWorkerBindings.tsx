import { useEffect, useState } from "react";

import { listOneShotDequeueWorkerBindings } from "../../api/oneShotDequeueWorkerBinding";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotDequeueWorkerBindingV1 } from "../../types/oneShotDequeueWorkerBinding";
import { WorkerBindingActivationPreflights } from "./WorkerBindingActivationPreflights";

const BLOCKERS: Record<string, string> = {
    store_contact_not_defined: "Store contact is not defined",
    runtime_contact_not_defined: "Runtime contact is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
};

export function OneShotDequeueWorkerBindings({ candidateId, dequeueId }: { candidateId: string; dequeueId: string }) {
    const [items, setItems] = useState<OneShotDequeueWorkerBindingV1[] | null>(null);
    const [error, setError] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listOneShotDequeueWorkerBindings(candidateId)
            .then((value) => { if (current) { setItems(value.items.filter((item) => item.one_shot_controlled_dequeue.dequeue_id === dequeueId)); setError(false); } })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, dequeueId, readAttempt]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="One-shot dequeue worker binding evidence">
        <h6 className="font-semibold">Worker binding</h6>
        <p className="mt-2 text-sm">This record links the approved queue item to a worker reference. It does not enable or contact the worker.</p>
        {items === null && !error && <p role="status" className="mt-3">Checking the worker record…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Atlas could not load the worker record. Retry to check its status.</p><p className="text-xs text-slate-400">Private system details are hidden.</p><button type="button" onClick={() => { setItems(null); setError(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {items?.length === 0 && !error && <p role="status" className="mt-3">No worker record has been saved.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="One-shot dequeue worker bindings">{items.map((item) => <Binding key={item.binding_id} item={item} />)}</ol>}
    </section>;
}

function Binding({ item }: { item: OneShotDequeueWorkerBindingV1 }) {
    const worker = item.worker_intake_admission.worker_identity;
    const intake = item.worker_intake_admission.worker_intake_reference;
    const limits = item.worker_intake_admission.inherited_limits;
    const status = isExpired(item.valid_until) ? "Expired" : "Saved";
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Worker binding {status.toLowerCase()}</p>
        <p className="mt-1">The worker has not been contacted or started. Execution is unavailable.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(item.recorded_at)} · Expires {formatUtcTimestamp(item.valid_until)}</p>
        <details className="mt-3">
            <summary>Technical details</summary>
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
                <Value name="Worker intake reference" value={intake.worker_intake_reference_id} />
                <Value name="Worker intake protocol" value={intake.intake_protocol} />
                <Value name="Queue item reference fingerprint" value={item.queue_item_reference_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Blockers</h6>
            <ol aria-label="Ordered one-shot dequeue worker binding blockers" className="mt-2 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
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
            <p className="mt-3 text-xs">Permanent binding subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · credential material present: false · endpoint material present: false · command material present: false.</p>
            <dl aria-label="One-shot dequeue worker binding fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Caller-supplied credentials allowed", "Caller-supplied endpoint allowed", "Caller-supplied command allowed", "Store contact allowed", "Runtime contact allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue acknowledgement allowed", "Queue mutation allowed", "Worker contact allowed", "Worker start allowed", "Agent invocation allowed", "Execution start allowed", "Process execution allowed", "Dispatch allowed", "Retry allowed", "Workflow start allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <WorkerBindingActivationPreflights candidateId={item.candidate_record_id} bindingId={item.binding_id} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
