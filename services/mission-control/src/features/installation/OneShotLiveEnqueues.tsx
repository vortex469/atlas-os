import { useEffect, useState } from "react";

import { listOneShotLiveEnqueues } from "../../api/oneShotLiveEnqueue";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotLiveEnqueueV1 } from "../../types/oneShotLiveEnqueue";

const BLOCKERS: Record<string, string> = {
    dequeue_not_defined: "Dequeue is not defined",
    queue_polling_not_defined: "Queue polling is not defined",
    worker_start_not_defined: "Worker start is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
};

export function OneShotLiveEnqueues({ candidateId, liveEnqueueAdmissionId, homeAssistantBlocked }: { candidateId: string; liveEnqueueAdmissionId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<OneShotLiveEnqueueV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listOneShotLiveEnqueues(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.lineage.live_enqueue_admission_id === liveEnqueueAdmissionId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, liveEnqueueAdmissionId]);

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="One-shot live enqueue evidence">
        <h6 className="font-semibold">One-shot live enqueue</h6>
        <p className="mt-2 text-sm">Mission Control presents Core-owned one-shot live enqueue evidence under the v0.41 admission. The item is inert and reference-only.</p>
        <p className="mt-2 text-sm">This is not dequeue, queue polling, worker contact, worker start, Agent invocation, workflow start, process execution, installation, provider mutation, repository mutation, in-guest mutation, deployment, rollback, retry, or resend.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">For Home Assistant, one-shot live enqueue remains blocked; it stays non-installable and non-executable.</p>}
        {items === null && !error && <p role="status" className="mt-3">Loading one-shot live enqueue evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>One-shot live enqueue evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, endpoint, worker address, queue detail, broker, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No one-shot live enqueue evidence has been recorded. Dequeue, queue polling, worker start, Agent invocation, workflow start, retry, resend, and execution remain blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="One-shot live enqueues">{items.map((item) => <OneShot key={item.enqueue_id} item={item} />)}</ol>}
    </section>;
}

function OneShot({ item }: { item: OneShotLiveEnqueueV1 }) {
    const status = isExpired(item.valid_until) ? "Expired" : "Recorded";
    const lineage = item.lineage;
    const queueItem = item.queue_item;
    const limits = item.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status} one-shot live enqueue evidence</p>
        <p className="mt-1">Outcome: {item.outcome}; lifecycle: {item.lifecycle}; inert reference-only item: true; payload constructed: false; payload serialized: false; dequeue defined: false; queue polling allowed: false.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Freshness is at most 30 seconds and expiry is passive.</p>
        <ol aria-label="Ordered one-shot live enqueue blockers" className="mt-2 list-decimal pl-5">
            {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
        </ol>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            <Value name="Queue item" value={queueItem.queue_item_id} />
            <Value name="Item kind" value={queueItem.item_kind} />
            <Value name="Live enqueue admission" value={lineage.live_enqueue_admission_id} />
            <Value name="Worker intake admission" value={lineage.worker_intake_admission_id} />
            <Value name="Queue reservation" value={lineage.queue_reservation_id} />
            <Value name="Queue item reference" value={lineage.queue_item_reference_id} />
        </dl>
        <details className="mt-3">
            <summary>Advanced one-shot enqueue evidence</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Enqueue ID" value={item.enqueue_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Record fingerprint" value={item.record_fingerprint.value} />
                <Value name="Item subject fingerprint" value={item.item_subject_fingerprint.value} />
                <Value name="Request fingerprint" value={item.request_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint.value} />
                <Value name="Item fingerprint" value={queueItem.item_fingerprint.value} />
                <Value name="Lineage fingerprint" value={lineage.lineage_fingerprint.value} />
                <Value name="v0.20-v0.41 chain fingerprint" value={lineage.v020_v041_chain_fingerprint.value} />
                <Value name="Live enqueue admission fingerprint" value={lineage.live_enqueue_admission_fingerprint.value} />
                <Value name="Live enqueue admission status fingerprint" value={lineage.live_enqueue_admission_status_fingerprint.value} />
                <Value name="Worker intake admission fingerprint" value={lineage.worker_intake_admission_fingerprint.value} />
                <Value name="Queue reservation fingerprint" value={lineage.queue_reservation_fingerprint.value} />
                <Value name="Queue intake reference fingerprint" value={lineage.queue_intake_reference_fingerprint.value} />
                <Value name="Queue item reference fingerprint" value={lineage.queue_item_reference_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Inherited sandbox, resource, network, and filesystem ceilings</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privileged / escalation / host namespaces / devices" value="false" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Inherited limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">Permanent one-shot subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · consumed: false · released: false · retry allowed: false · resend allowed: false · replay bypass allowed: false.</p>
            <p className="mt-2 text-xs">Audit and errors are server-owned, redacted, and fingerprint-bound; Mission Control displays only identifiers and fingerprints returned by Core.</p>
            <dl aria-label="One-shot live enqueue fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Payload schema defined", "Payload constructed", "Payload serialized", "Dequeue defined", "Dequeue allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue ack allowed", "Worker contact allowed", "Worker authentication allowed", "Worker binding allowed", "Worker start allowed", "Execution start allowed", "Runner binding allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Scheduler allowed", "Docker execution allowed", "Podman execution allowed", "Container execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
