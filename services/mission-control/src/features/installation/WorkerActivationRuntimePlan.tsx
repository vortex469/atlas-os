import { WorkerActivationRuntimePlanReview } from "./WorkerActivationRuntimePlanReview";
import { useEffect, useState } from "react";
import { getWorkerActivationRuntimePlan } from "../../api/workerActivationRuntimePlan";
import type { WorkerActivationRuntimeAdmission } from "../../types/workerActivationRuntimeAdmission";
import type { WorkerActivationRuntimePlan as Evidence } from "../../types/workerActivationRuntimePlan";

export function WorkerActivationRuntimePlan({ admission }: { admission: WorkerActivationRuntimeAdmission }) {
    return <PlanReader key={JSON.stringify(admission)} admission={admission} />;
}

function PlanReader({ admission }: { admission: WorkerActivationRuntimeAdmission }) {
    // The keyed reader owns one evidence scope. Equivalent parent renders must
    // not trigger background reads while the previous Core status stays visible.
    const [scope] = useState(admission);
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    const [readAttempt, setReadAttempt] = useState(0);
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimePlan(scope)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [scope, readAttempt]);
    return <section aria-label="Worker runtime plan state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Runtime plan review</h6>
        <p>A saved plan is reference-only. It does not set up or start a runtime; worker start and execution are unavailable.</p>
        {state === "loading" && <p role="status">Checking the runtime plan…</p>}
        {state === "missing" && <p role="status">No runtime plan has been saved for this admission.</p>}
        {state === "unavailable" && <div role="alert"><p>Atlas could not load the runtime plan. Retry to check its status.</p><button type="button" onClick={() => { setState("loading"); setReadAttempt((attempt) => attempt + 1); }} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {typeof state === "object" && <>
            <p>Reference-only runtime plan saved.</p>
            <p>{state.lifecycle === "expired" ? "This plan has expired." : "This plan is current."}</p>
            <details className="mt-3">
                <summary>Technical details</summary>
                <dl>{Object.entries({ "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Reference-only design">{JSON.stringify(state.design, null, 2)}</pre>
                <pre aria-label="Exact admission lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.55 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimePlanReview plan={state} />
        </>}
    </section>;
}
