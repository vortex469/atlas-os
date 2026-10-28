import { useEffect, useState } from "react";
import { WorkerActivationRuntimePrerequisite } from "./WorkerActivationRuntimePrerequisite";
import { getControlledWorkerQueueReceipt } from "../../api/controlledWorkerQueueReceipt";
import type { ControlledWorkerQueueReceipt as Receipt } from "../../types/controlledWorkerQueueReceipt";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

export function ControlledWorkerQueueReceipt(props: { candidateId: string; admissionId: string; operatorId: string }) {
    // Remount the reader on scope changes so another owner's evidence cannot flash.
    return <ReceiptReader key={JSON.stringify(props)} {...props} />;
}

function ReceiptReader({ candidateId, admissionId, operatorId }: { candidateId: string; admissionId: string; operatorId: string }) {
    const [receipt, setReceipt] = useState<Receipt | null>(null);
    const [unavailable, setUnavailable] = useState(false);
    useEffect(() => {
        let current = true;
        getControlledWorkerQueueReceipt(candidateId, admissionId, operatorId)
            .then((value) => { if (current) setReceipt(value); })
            .catch(() => { if (current) setUnavailable(true); });
        return () => { current = false; };
    }, [candidateId, admissionId, operatorId]);

    return <section aria-label="Controlled queue receipt state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Queue receipt</h6>
        <p>This is read-only evidence from Core. It does not authorize queue operations, worker start, or execution.</p>
        {!receipt && !unavailable && <p role="status">Loading queue receipt...</p>}
        {unavailable && <p role="status">Receipt is unavailable or not recorded. No queue outcome is confirmed.</p>}
        {receipt && <>
            <p className="mt-2 font-semibold">Core recorded evidence for a queue claim, lease, and acknowledgement.</p>
            <p>{receipt.lifecycle === "expired" ? "This receipt has expired." : "This receipt is current."}</p>
            <BlockerSummary blockers={receipt.blockers} />
            <p className="mt-2">Worker start and execution remain blocked.</p>
            <p>Recorded {formatDateTime(receipt.recordedAt)} · Expires {formatDateTime(receipt.validUntil)}.</p>
            <details className="mt-3">
                <summary>Advanced details</summary>
                <dl className="mt-2 space-y-2">
                    {Object.entries({ "Admission ID": receipt.admissionId, "Candidate ID": receipt.candidateId, "Operator ID": receipt.operatorId, "Recorded at": receipt.recordedAt, "Valid until": receipt.validUntil, "Core evaluated at": receipt.evaluatedAt, "Reservation before effect": String(receipt.reservationBeforeEffect), ...Object.fromEntries(Object.entries(receipt.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}
                </dl>
                <p className="mt-2">Blockers</p>
                <ol aria-label="Ordered queue receipt blockers">{receipt.blockers.map((blocker) => <li key={blocker}>{workerBindingActivationBlockerLabel(blocker)} <code>{blocker}</code></li>)}</ol>
                <dl aria-label="v0.52 fixed-false authority">{Object.entries(receipt.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimePrerequisite receipt={receipt} />
        </>}
    </section>;
}

function BlockerSummary({ blockers }: { blockers: Receipt["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-1">No blockers are listed. This receipt still grants no permission to start a worker.</p>;
    return <div className="mt-2 rounded border border-amber-500/40 p-2" aria-label="Worker start status">
        <p className="font-semibold">Worker start remains blocked</p>
        <p>{blockers.length} {blockers.length === 1 ? "requirement remains" : "requirements remain"} unavailable.</p>
        <details className="mt-1">
            <summary>Show what remains</summary>
            <ul aria-label="Worker start blockers" className="mt-2 list-disc pl-5">
                {blockers.map((blocker) => <li key={blocker}>{workerBindingActivationBlockerLabel(blocker)}</li>)}
            </ul>
        </details>
    </div>;
}

function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
