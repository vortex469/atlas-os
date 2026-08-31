import { useEffect, useState } from "react";
import { listWorkerQueueReservations } from "../../api/workerQueueReservation";
import type { WorkerQueueReservationResultV1 } from "../../types/workerQueueReservation";

export function WorkerQueueReservations({ candidateId, stubId, homeAssistantBlocked }: { candidateId: string; stubId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<WorkerQueueReservationResultV1[] | null>(null); const [error, setError] = useState(false);
    useEffect(() => { let current = true; listWorkerQueueReservations(candidateId).then((value) => { if (current) setItems(value.items.filter((item) => item.reservation?.linkage.worker_admission_stub_id === stubId)); }).catch(() => { if (current) setError(true); }); return () => { current = false; }; }, [candidateId, stubId]);
    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Worker queue reservation evidence">
        <h6 className="font-semibold">Worker queue reservation evidence</h6>
        <p className="mt-2 text-sm">This preserves an evidence-only worker queue reservation record. It is default-disabled and does not create or contact a live queue.</p>
        <p className="mt-2 text-sm">This is not live enqueue, dequeue, worker start, dispatch, execution, Agent invocation, workflow start, provider mutation, repository mutation, in-guest mutation, installation, deployment, rollback, retry, resend, or permission to mutate anything.</p>
        <p className="mt-2 text-sm">Creation is unavailable here because Core supplies no eligible server-owned queue reference context. Mission Control does not invent references, edit inherited ceilings, poll, or integrate with a queue.</p>
        {homeAssistantBlocked && <p className="mt-2 text-sm text-amber-200">For Home Assistant, queue reservation remains blocked; it stays non-installable and non-executable.</p>}
        {items === null && !error && <p role="status">Loading worker queue reservation evidence…</p>}
        {error && <div role="alert"><p>Worker queue reservation evidence is unavailable.</p><p className="text-xs">The error is redacted; no credential, payload, command, log, address, endpoint, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status">No worker queue reservation evidence has been recorded. Enqueue, dequeue, worker start, dispatch, and execution remain blocked.</p>}
        {items && <ol className="mt-3 space-y-3">{items.map((result) => <Reservation key={result.reservation!.reservation_id} result={result} />)}</ol>}
    </section>;
}

function Reservation({ result }: { result: WorkerQueueReservationResultV1 }) {
    const record = result.reservation!; const status = result.status!; const intake = record.queue_intake_reference; const item = record.queue_item_reference; const link = record.linkage; const limits = record.inherited_limits; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status.lifecycle} {status.eligibility} evidence</p><p>Owner: {record.operator_id} · recorded: {record.recorded_at} · valid until: {record.valid_until} · observed: {status.observed_at}. Freshness is at most 30 seconds and expiry is passive.</p>
        <ol aria-label="Ordered queue reservation blockers">{status.blockers.map((value) => <li key={value}>{value}</li>)}</ol>
        <dl className="grid gap-2 sm:grid-cols-2"><Value n="Queue intake reference" v={intake.queue_intake_reference_id} /><Value n="Queue intake fingerprint" v={intake.reference_fingerprint.value} /><Value n="Queue kind" v={intake.queue_kind} /><Value n="Queue eligibility" v={intake.eligibility} /><Value n="Queue item reference" v={item.queue_item_reference_id} /><Value n="Queue item fingerprint" v={item.item_fingerprint.value} /><Value n="Item kind" v={item.item_kind} /><Value n="Record fingerprint" v={record.record_fingerprint.value} /><Value n="Status fingerprint" v={status.status_fingerprint.value} /></dl>
        <details open><summary>Inherited byte-exact sandbox, resource, network, and filesystem ceilings</summary><dl><Value n="Sandbox" v={limits.sandbox.profile} /><Value n="CPU millis" v={String(limits.resources.cpu_millis_max)} /><Value n="Memory bytes" v={String(limits.resources.memory_bytes_max)} /><Value n="PID ceiling" v={String(limits.resources.pids_max)} /><Value n="Network" v={limits.network.mode} /><Value n="Writable scope" v={limits.filesystem.writable_scope} /><Value n="Limits fingerprint" v={limits.limits_fingerprint.value} /></dl></details>
        <details><summary>Required v0.20–v0.38 linkage fingerprints</summary><dl><Value n="v0.20–v0.37 chain" v={link.v020_v037_chain_fingerprint.value} /><Value n="v0.34 readiness" v={link.readiness_review_fingerprint.value} /><Value n="v0.35 permission grant" v={link.permission_grant_fingerprint.value} /><Value n="v0.36 admission" v={link.execution_admission_fingerprint.value} /><Value n="v0.37 runner binding" v={link.runner_binding_plan_fingerprint.value} /><Value n="v0.38 worker admission" v={link.worker_admission_stub_fingerprint.value} /><Value n="Linkage fingerprint" v={link.linkage_fingerprint.value} /></dl></details>
        <p>Permanent queue-subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · consumed: false · released: false · retry: false · replay bypass: false.</p>
        <p>Audit: {audit.event} / {audit.outcome} · {audit.audit_fingerprint.value} · correlation {audit.correlation_fingerprint.value}</p>
        <dl aria-label="Queue reservation fixed-false authority fields">{["Live enqueue", "Dequeue", "Worker start", "Dispatch", "Execution", "Agent invocation", "Workflow start", "Provider mutation", "Repository mutation", "In-guest mutation", "Installation", "Deployment", "Rollback", "Retry", "Resend", "Replay bypass"].map((name) => <Value key={name} n={name} v="false" />)}</dl>
    </li>;
}
function Value({ n, v }: { n: string; v: string }) { return <div><dt>{n}</dt><dd className="break-all">{v}</dd></div>; }
