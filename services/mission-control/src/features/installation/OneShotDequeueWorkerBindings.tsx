import { useEffect, useState } from "react";

import { listOneShotDequeueWorkerBindings } from "../../api/oneShotDequeueWorkerBinding";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotDequeueWorkerBindingV1 } from "../../types/oneShotDequeueWorkerBinding";

const BLOCKERS: Record<string, string> = {
    store_contact_not_defined: "Store contact is not defined",
    runtime_contact_not_defined: "Runtime contact is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
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

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="One-shot dequeue worker binding evidence">
        <h6 className="font-semibold">One-shot dequeue worker binding</h6>
        <p className="mt-2 text-sm">Mission Control shows v0.46 binding evidence inside the existing installation workflow. It is evidence only and does not contact a store, runtime, queue, worker, Agent, shell, or process.</p>
        <p className="mt-1 text-sm">No worker-start, Agent invocation, execution, installation, deployment, rollback, retry, resend, queue mutation, provider mutation, repository mutation, or in-guest mutation control is available here.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading one-shot dequeue worker binding evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>One-shot dequeue worker binding evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no credential, endpoint, command, payload, queue detail, worker address, broker, log, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No one-shot dequeue worker binding evidence has been recorded. Worker start, Agent invocation, and execution remain blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="One-shot dequeue worker bindings">{items.map((item) => <Binding key={item.binding_id} item={item} />)}</ol>}
    </section>;
}

function Binding({ item }: { item: OneShotDequeueWorkerBindingV1 }) {
    const worker = item.worker_intake_admission.worker_identity;
    const intake = item.worker_intake_admission.worker_intake_reference;
    const limits = item.worker_intake_admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Recorded one-shot dequeue worker binding evidence</p>
        <p className="mt-1">State: eligible; bound: readiness gated; blocked: yes. Store contacted: false; runtime contacted: false; worker started: false; execution started: false.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Expiry is passive and never contacts a worker, starts execution, or retries delivery.</p>
        <details className="mt-3">
            <summary>Advanced details</summary>
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
    </li>;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
