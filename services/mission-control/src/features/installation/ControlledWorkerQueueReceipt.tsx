import { useEffect, useState } from "react";
import { WorkerActivationRuntimePrerequisite } from "./WorkerActivationRuntimePrerequisite";
import { getControlledWorkerQueueReceipt } from "../../api/controlledWorkerQueueReceipt";
import type { ControlledWorkerQueueReceipt as Receipt } from "../../types/controlledWorkerQueueReceipt";

export function ControlledWorkerQueueReceipt(props: { candidateId: string; admissionId: string; operatorId: string }) {
    // Remount the reader on scope changes so another owner's evidence cannot flash.
    return <ReceiptReader key={JSON.stringify(props)} {...props} />;
}

function ReceiptReader({ candidateId, admissionId, operatorId }: { candidateId: string; admissionId: string; operatorId: string }) {
    const [receipt, setReceipt] = useState<Receipt | null>(null);
    const [unavailable, setUnavailable] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);
    useEffect(() => {
        let current = true;
        getControlledWorkerQueueReceipt(candidateId, admissionId, operatorId)
            .then((value) => { if (current) { setReceipt(value); setUnavailable(false); } })
            .catch(() => { if (current) setUnavailable(true); });
        return () => { current = false; };
    }, [candidateId, admissionId, operatorId, readAttempt]);

    return <section aria-label="Queue review state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Queue review status</h6>
        <p>Queue work and worker start are unavailable. This screen only shows Core review evidence.</p>
        {!receipt && !unavailable && <p role="status" className="mt-2">Checking the saved queue review…</p>}
        {unavailable && <div role="alert" className="mt-2"><p>The queue review is unavailable or has not been saved. No queue outcome is confirmed.</p><button type="button" onClick={() => { setReceipt(null); setUnavailable(false); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {receipt && <>
            <p className="mt-2 font-semibold">Queue review saved.</p>
            <p>{receipt.lifecycle === "expired" ? "This review has expired." : "This review is current."}</p>
            <details className="mt-3">
                <summary>Technical details</summary>
                <dl className="mt-2 space-y-2">
                    {Object.entries({ "Admission ID": receipt.admissionId, "Candidate ID": receipt.candidateId, "Operator ID": receipt.operatorId, "Recorded at": receipt.recordedAt, "Valid until": receipt.validUntil, "Core evaluated at": receipt.evaluatedAt, "Reservation before effect": String(receipt.reservationBeforeEffect), ...Object.fromEntries(Object.entries(receipt.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}
                </dl>
                <p className="mt-2">Core reason codes</p>
                <ol>{receipt.blockers.map((blocker) => <li key={blocker}><code>{blocker}</code></li>)}</ol>
                <dl aria-label="v0.52 fixed-false authority">{Object.entries(receipt.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimePrerequisite receipt={receipt} />
        </>}
    </section>;
}
