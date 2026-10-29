import { WorkerActivationRuntimePlan } from "./WorkerActivationRuntimePlan";
import { useEffect, useState } from "react";
import { getWorkerActivationRuntimeAdmission } from "../../api/workerActivationRuntimeAdmission";
import type { WorkerActivationRuntimePrerequisite } from "../../types/workerActivationRuntimePrerequisite";
import type { WorkerActivationRuntimeAdmission as Evidence } from "../../types/workerActivationRuntimeAdmission";

export function WorkerActivationRuntimeAdmission({ prerequisite }: { prerequisite: WorkerActivationRuntimePrerequisite }) {
    return <AdmissionReader key={JSON.stringify(prerequisite)} prerequisite={prerequisite} />;
}

function AdmissionReader({ prerequisite }: { prerequisite: WorkerActivationRuntimePrerequisite }) {
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    const [readAttempt, setReadAttempt] = useState(0);
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimeAdmission(prerequisite)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [prerequisite, readAttempt]);
    return <section aria-label="Worker runtime admission state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Runtime admission review</h6>
        <p>Runtime requirements are not met. Worker start and execution are unavailable.</p>
        {state === "loading" && <p role="status">Checking the runtime review…</p>}
        {state === "missing" && <p role="status">No runtime admission review has been saved for this prerequisite.</p>}
        {state === "unavailable" && <div role="alert"><p>Atlas could not load the runtime admission review. Retry to check its status.</p><button type="button" onClick={() => { setState("loading"); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {typeof state === "object" && <>
            <p>Runtime admission review saved. This record supports future design only; it does not enable a runtime or start a worker.</p>
            <p>{state.lifecycle === "expired" ? "This review has expired." : "This review is current."}</p>
            <details className="mt-3">
                <summary>Technical details</summary>
                <dl>{Object.entries({ "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Exact prerequisite lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.54 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimePlan admission={state} />
        </>}
    </section>;
}
