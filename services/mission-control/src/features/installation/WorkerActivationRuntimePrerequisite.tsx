import { useEffect, useState } from "react";
import { getWorkerActivationRuntimePrerequisite } from "../../api/workerActivationRuntimePrerequisite";
import type { ControlledWorkerQueueReceipt } from "../../types/controlledWorkerQueueReceipt";
import type { WorkerActivationRuntimePrerequisite as Evidence } from "../../types/workerActivationRuntimePrerequisite";

export function WorkerActivationRuntimePrerequisite({ receipt }: { receipt: ControlledWorkerQueueReceipt }) {
    return <PrerequisiteReader key={JSON.stringify(receipt)} receipt={receipt} />;
}

function PrerequisiteReader({ receipt }: { receipt: ControlledWorkerQueueReceipt }) {
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimePrerequisite(receipt)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [receipt]);
    return <section aria-label="Worker runtime prerequisite state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Worker runtime prerequisites</h6>
        <p>Runtime prerequisites remain incomplete. Worker start and execution remain blocked.</p>
        <p>Mission Control only displays Core evidence.</p>
        {state === "loading" && <p role="status">Loading runtime prerequisite state...</p>}
        {state === "missing" && <p role="status">Core has no recorded runtime prerequisite evidence for this queue receipt.</p>}
        {state === "unavailable" && <p role="status">Runtime prerequisite evidence is unavailable. No runtime outcome can be confirmed.</p>}
        {typeof state === "object" && <>
            <p>Core recorded prerequisite evidence for this queue receipt.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this prerequisite evidence has expired." : "Core reports this prerequisite evidence is active."}</p>
            <details className="mt-3">
                <summary>Advanced v0.53 evidence</summary>
                <dl>{Object.entries({ "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.53 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
        </>}
    </section>;
}
