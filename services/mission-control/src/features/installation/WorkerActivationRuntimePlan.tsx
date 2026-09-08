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
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimePlan(scope)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [scope]);
    return <section aria-label="Worker runtime plan state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Worker runtime plan evidence</h6>
        <p>Runtime plan is evidence; runtime prerequisites remain incomplete. Worker start and execution remain blocked.</p>
        <p>Mission Control only displays Core evidence.</p>
        {state === "loading" && <p role="status">Loading runtime plan state...</p>}
        {state === "missing" && <p role="status">Core has no recorded runtime plan evidence for this admission.</p>}
        {state === "unavailable" && <p role="status">Runtime plan evidence is unavailable. No runtime outcome can be confirmed.</p>}
        {typeof state === "object" && <>
            <p>Core recorded a reference-only runtime plan for this admission.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this plan evidence has expired." : "Core reports this plan evidence is active."}</p>
            <details className="mt-3">
                <summary>Advanced v0.55 evidence</summary>
                <dl>{Object.entries({ "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Reference-only design">{JSON.stringify(state.design, null, 2)}</pre>
                <pre aria-label="Exact admission lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.55 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
        </>}
    </section>;
}
