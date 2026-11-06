import { useEffect, useState } from "react";

import { listOneShotLiveEnqueues } from "../../api/oneShotLiveEnqueue";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { OneShotLiveEnqueueV1 } from "../../types/oneShotLiveEnqueue";
import { QueueObservationEvidence } from "./QueueObservationEvidence";

const BLOCKERS: Record<string, string> = {
    dequeue_not_defined: "Atlas has not set up a way to remove queued work.",
    queue_polling_not_defined: "Atlas has not set up a way to read work from a queue.",
    worker_start_not_defined: "Atlas has not set up a way to start a worker.",
    execution_start_boundary_not_defined: "Atlas has not set up a safe way to start this installation.",
};

export function OneShotLiveEnqueues({ candidateId, liveEnqueueAdmissionId }: { candidateId: string; liveEnqueueAdmissionId: string }) {
    const [items, setItems] = useState<OneShotLiveEnqueueV1[] | null>(null);
    const [error, setError] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listOneShotLiveEnqueues(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.lineage.live_enqueue_admission_id === liveEnqueueAdmissionId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, liveEnqueueAdmissionId, readAttempt]);

    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Queue item record">
        <h6 className="font-semibold">Queue item record</h6>
        <p className="mt-2 text-sm">Core saved an inert item reference. It has no payload and cannot be consumed or run.</p>
        {items === null && !error && <p role="status" className="mt-3">Checking for a saved queue item record…</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Atlas could not load the queue item record. Retry to check its current status.</p><p className="text-xs text-slate-400">Private system details are hidden.</p><button type="button" onClick={() => { setItems(null); setError(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No queue item record has been saved. Queue consumption and worker start remain unavailable.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Saved queue item records">{items.map((item) => <OneShot key={item.enqueue_id} item={item} />)}</ol>}
    </section>;
}

function OneShot({ item }: { item: OneShotLiveEnqueueV1 }) {
    const expired = isExpired(item.valid_until);
    const lineage = item.lineage;
    const queueItem = item.queue_item;
    const limits = item.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{expired ? "Queue item record has expired" : "Queue item record is current"}</p>
        <p className="mt-1">This reference has no payload and has not contacted a worker.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(item.recorded_at)}; valid until {formatUtcTimestamp(item.valid_until)}. An expired record cannot be renewed.</p>
        <ol aria-label="What needs attention" className="mt-2 list-decimal pl-5">
            {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? "Atlas reported an issue that needs review."}</li>)}
        </ol>
        <details className="mt-3">
            <summary>Technical details</summary>
            <p className="mt-2">Record outcome: {item.outcome}; lifecycle: {item.lifecycle}; item kind: {queueItem.item_kind}.</p>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Queue item ID" value={queueItem.queue_item_id} />
                <Value name="Live enqueue admission" value={lineage.live_enqueue_admission_id} />
                <Value name="Worker intake admission" value={lineage.worker_intake_admission_id} />
                <Value name="Queue reservation" value={lineage.queue_reservation_id} />
                <Value name="Queue item reference" value={lineage.queue_item_reference_id} />
            </dl>
            <details className="mt-3"><summary>Blocker codes</summary><ul className="mt-2 list-disc pl-5">{item.blockers.map((value) => <li key={value}><code>{value}</code></li>)}</ul></details>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Enqueue ID" value={item.enqueue_id} />
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
            <details className="mt-3"><summary>Sandbox and resource limits</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privileged / escalation / host namespaces / devices" value="false" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Inherited limits fingerprint" value={limits.limits_fingerprint.value} />
            </dl></details>
            <p className="mt-3 text-xs">Permanent one-shot subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · consumed: false · released: false · retry allowed: false · resend allowed: false · replay bypass allowed: false.</p>
            <p className="mt-2 text-xs">Audit and errors are server-owned, redacted, and fingerprint-bound; Mission Control displays only identifiers and fingerprints returned by Core.</p>
            <dl aria-label="One-shot live enqueue fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Payload schema defined", "Payload constructed", "Payload serialized", "Dequeue defined", "Dequeue allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue ack allowed", "Worker contact allowed", "Worker authentication allowed", "Worker binding allowed", "Worker start allowed", "Execution start allowed", "Runner binding allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Agent invocation allowed", "Workflow start allowed", "Scheduler allowed", "Docker execution allowed", "Podman execution allowed", "Container execution allowed", "Shell execution allowed", "Process execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <QueueObservationEvidence candidateId={item.candidate_record_id} oneShot={item} />
    </li>;
}

function isExpired(value: string) {
    const expiry = Date.parse(value);
    return Number.isFinite(expiry) && expiry <= Date.now();
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
