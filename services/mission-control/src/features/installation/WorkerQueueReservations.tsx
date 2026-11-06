import { useEffect, useState } from "react";
import { listWorkerQueueReservations } from "../../api/workerQueueReservation";
import type { WorkerQueueReservationResultV1 } from "../../types/workerQueueReservation";
import { WorkerIntakeAdmissions } from "./WorkerIntakeAdmissions";

const BLOCKER_LABELS: Record<string, string> = {
    live_enqueue_not_defined: "Atlas has not set up a live queue.",
    dequeue_not_defined: "Atlas has not set up a way to remove queued work.",
    worker_start_not_defined: "Atlas has not set up a way to start a worker.",
    execution_start_boundary_not_defined: "Atlas has not set up a safe way to start this installation.",
};

export function WorkerQueueReservations({ candidateId, stubId, homeAssistantBlocked }: { candidateId: string; stubId: string; homeAssistantBlocked: boolean }) {
    const [items, setItems] = useState<WorkerQueueReservationResultV1[] | null>(null);
    const [error, setError] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);
    useEffect(() => {
        let current = true;
        listWorkerQueueReservations(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.reservation?.linkage.worker_admission_stub_id === stubId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, stubId, readAttempt]);
    return <section className="mt-4 rounded border border-slate-700 p-3" aria-label="Worker queue review">
        <h6 className="font-semibold">Queue review record</h6>
        <p className="mt-2 text-sm">This record does not connect to a live queue or put work on one.</p>
        <p className="mt-2 text-sm">Atlas has no eligible queue reference here, so it cannot save a queue review record. It does not search for or connect to queues.</p>
        {items === null && !error && <p role="status">Checking for a saved queue review record…</p>}
        {error && <div role="alert"><p>Atlas could not load the queue review record. Retry to check its current status.</p><p className="text-xs">Private system details are hidden.</p><button type="button" onClick={() => { setItems(null); setError(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {items?.length === 0 && <p role="status">No queue review record has been saved. Atlas cannot enqueue or start work.</p>}
        {items && <ol aria-label="Saved queue review records" className="mt-3 space-y-3">{items.map((result) => <Reservation key={result.reservation!.reservation_id} result={result} homeAssistantBlocked={homeAssistantBlocked} />)}</ol>}
    </section>;
}

function Reservation({ result, homeAssistantBlocked }: { result: WorkerQueueReservationResultV1; homeAssistantBlocked: boolean }) {
    const record = result.reservation!; const status = result.status!; const intake = record.queue_intake_reference; const item = record.queue_item_reference; const link = record.linkage; const limits = record.inherited_limits; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">{status.lifecycle === "active" ? "Queue review record is current" : "Queue review record has expired"}</p>
        <p className="mt-1">This record has not put work in a queue or started a worker.</p>
        <p className="mt-1">Saved {formatUtcTimestamp(record.recorded_at)}; valid until {formatUtcTimestamp(record.valid_until)}; checked {formatUtcTimestamp(status.observed_at)}. An expired record cannot be renewed.</p>
        <ol aria-label="What needs attention" className="mt-2 list-decimal pl-5">{status.blockers.map((value) => <li key={value}>{BLOCKER_LABELS[value] ?? "Atlas reported an issue that needs review."}</li>)}</ol>
        <details className="mt-3"><summary>Technical details</summary>
            <p className="mt-2">Record status: {status.eligibility}; result: {result.disposition}.</p>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value n="Owner" v={record.operator_id} /><Value n="Reservation ID" v={record.reservation_id} /><Value n="Queue intake reference" v={intake.queue_intake_reference_id} /><Value n="Queue intake fingerprint" v={intake.reference_fingerprint.value} /><Value n="Queue kind" v={intake.queue_kind} /><Value n="Queue eligibility" v={intake.eligibility} /><Value n="Queue item reference" v={item.queue_item_reference_id} /><Value n="Queue item fingerprint" v={item.item_fingerprint.value} /><Value n="Item kind" v={item.item_kind} /><Value n="Record fingerprint" v={record.record_fingerprint.value} /><Value n="Status fingerprint" v={status.status_fingerprint.value} /></dl>
            <details className="mt-3"><summary>Sandbox and resource limits</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value n="Sandbox" v={limits.sandbox.profile} /><Value n="CPU millis" v={String(limits.resources.cpu_millis_max)} /><Value n="Memory bytes" v={String(limits.resources.memory_bytes_max)} /><Value n="PID ceiling" v={String(limits.resources.pids_max)} /><Value n="Network" v={limits.network.mode} /><Value n="Writable scope" v={limits.filesystem.writable_scope} /><Value n="Limits fingerprint" v={limits.limits_fingerprint.value} /></dl></details>
            <details className="mt-3"><summary>Related review records</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2"><Value n="v0.20–v0.37 chain" v={link.v020_v037_chain_fingerprint.value} /><Value n="v0.34 readiness" v={link.readiness_review_fingerprint.value} /><Value n="v0.35 permission grant" v={link.permission_grant_fingerprint.value} /><Value n="v0.36 admission" v={link.execution_admission_fingerprint.value} /><Value n="v0.37 runner binding" v={link.runner_binding_plan_fingerprint.value} /><Value n="v0.38 worker admission" v={link.worker_admission_stub_fingerprint.value} /><Value n="Linkage fingerprint" v={link.linkage_fingerprint.value} /></dl></details>
            <p className="mt-3">This record cannot be retried or replayed. Audit: {audit.event} / {audit.outcome}.</p>
            <dl aria-label="Queue reservation fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Live enqueue", "Dequeue", "Worker start", "Dispatch", "Execution", "Agent invocation", "Workflow start", "Provider mutation", "Repository mutation", "In-guest mutation", "Installation", "Deployment", "Rollback", "Retry", "Resend", "Replay bypass"].map((name) => <Value key={name} n={name} v="false" />)}</dl>
        </details>
        <WorkerIntakeAdmissions candidateId={record.candidate_record_id} reservationId={record.reservation_id} homeAssistantBlocked={homeAssistantBlocked} />
    </li>;
}
function Value({ n, v }: { n: string; v: string }) { return <div><dt>{n}</dt><dd className="break-all">{v}</dd></div>; }
function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
