import { WorkerActivationRuntimeAdmission } from "./WorkerActivationRuntimeAdmission";
import { useEffect, useState } from "react";
import { getWorkerActivationRuntimePrerequisite } from "../../api/workerActivationRuntimePrerequisite";
import type { ControlledWorkerQueueReceipt } from "../../types/controlledWorkerQueueReceipt";
import type { WorkerActivationRuntimePrerequisite as Evidence } from "../../types/workerActivationRuntimePrerequisite";

export function WorkerActivationRuntimePrerequisite({ receipt }: { receipt: ControlledWorkerQueueReceipt }) {
    return <PrerequisiteReader key={JSON.stringify(receipt)} receipt={receipt} />;
}

function PrerequisiteReader({ receipt }: { receipt: ControlledWorkerQueueReceipt }) {
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    const [readAttempt, setReadAttempt] = useState(0);
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimePrerequisite(receipt)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [receipt, readAttempt]);
    return <section aria-label="Worker runtime prerequisite state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Runtime readiness review</h6>
        <p>Runtime setup is incomplete. Worker start and execution are unavailable.</p>
        {state === "loading" && <p role="status">Checking runtime requirements…</p>}
        {state === "missing" && <p role="status">No runtime review has been saved for this queue record.</p>}
        {state === "unavailable" && <div role="alert"><p>Atlas could not load the runtime review. Retry to check its status.</p><button type="button" onClick={() => { setState("loading"); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {typeof state === "object" && <>
            <p>Runtime review saved for this queue record.</p>
            <p>{state.lifecycle === "expired" ? "This review has expired." : "This review is current."}</p>
            <p>This review does not create a runtime or start a worker.</p>
            <details className="mt-3">
                <summary>Technical details</summary>
                <dl>{Object.entries({ "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.53 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimeAdmission prerequisite={state} />
        </>}
    </section>;
}
