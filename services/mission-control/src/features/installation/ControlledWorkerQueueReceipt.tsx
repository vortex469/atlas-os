import { useEffect, useState } from "react";
import { getControlledWorkerQueueReceipt } from "../../api/controlledWorkerQueueReceipt";
import type { ControlledWorkerQueueReceipt as Receipt } from "../../types/controlledWorkerQueueReceipt";

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
        <h6 className="font-semibold">Queue claim, lease, and acknowledgement</h6>
        <p>Worker start and execution remain blocked. Mission Control only displays Core evidence.</p>
        {!receipt && !unavailable && <p role="status">Loading queue receipt state...</p>}
        {unavailable && <p role="status">Queue receipt evidence is unavailable or has not been recorded. No queue outcome can be confirmed.</p>}
        {receipt && <>
            <p className="mt-2 font-semibold">Core recorded the queue claim, lease, and acknowledgement.</p>
            <p>{receipt.lifecycle === "expired" ? "Core reports this evidence has expired." : "Core reports this evidence is active."}</p>
            <details className="mt-3">
                <summary>Advanced v0.52 evidence</summary>
                <dl className="mt-2 space-y-2">
                    {Object.entries({ "Admission ID": receipt.admissionId, "Candidate ID": receipt.candidateId, "Operator ID": receipt.operatorId, "Recorded at": receipt.recordedAt, "Valid until": receipt.validUntil, "Core evaluated at": receipt.evaluatedAt, "Reservation before effect": String(receipt.reservationBeforeEffect), ...Object.fromEntries(Object.entries(receipt.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}
                </dl>
                <p className="mt-2">Core reason codes</p>
                <ol>{receipt.blockers.map((blocker) => <li key={blocker}><code>{blocker}</code></li>)}</ol>
                <dl aria-label="v0.52 fixed-false authority">{Object.entries(receipt.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
        </>}
    </section>;
}
