import { WorkerActivationRuntimePlan } from "./WorkerActivationRuntimePlan";
import { useEffect, useState } from "react";
import { getWorkerActivationRuntimeAdmission } from "../../api/workerActivationRuntimeAdmission";
import type { WorkerActivationRuntimePrerequisite } from "../../types/workerActivationRuntimePrerequisite";
import type { WorkerActivationRuntimeAdmission as Evidence } from "../../types/workerActivationRuntimeAdmission";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

export function WorkerActivationRuntimeAdmission({ prerequisite }: { prerequisite: WorkerActivationRuntimePrerequisite }) {
    return <AdmissionReader key={JSON.stringify(prerequisite)} prerequisite={prerequisite} />;
}

function AdmissionReader({ prerequisite }: { prerequisite: WorkerActivationRuntimePrerequisite }) {
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimeAdmission(prerequisite)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [prerequisite]);
    return <section aria-label="Worker runtime admission state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Runtime design evidence</h6>
        <p>This Core record is for future runtime design. It does not authorize a worker or start execution.</p>
        {state === "loading" && <p role="status">Loading runtime design evidence...</p>}
        {state === "missing" && <p role="status">No runtime design record is available for this prerequisite.</p>}
        {state === "unavailable" && <p role="status">Runtime design evidence is unavailable. No runtime status is confirmed.</p>}
        {typeof state === "object" && <>
            <p className="mt-2 font-semibold">Runtime design record saved</p>
            <p>This is not runtime readiness. Worker start and execution remain blocked.</p>
            <p>{state.lifecycle === "expired" ? "This record has expired." : "This record is current."}</p>
            <BlockerSummary blockers={state.blockers} />
            <p className="mt-2">Recorded {formatDateTime(state.recordedAt)} · Expires {formatDateTime(state.validUntil)}.</p>
            <details className="mt-3">
                <summary>Advanced details</summary>
                <dl>{Object.entries({ "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Exact prerequisite lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Blockers</p>
                <ol aria-label="Ordered runtime design blockers">{state.blockers.map((code) => <li key={code}>{workerBindingActivationBlockerLabel(code)} <code>{code}</code></li>)}</ol>
                <dl aria-label="v0.54 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimePlan admission={state} />
        </>}
    </section>;
}

function BlockerSummary({ blockers }: { blockers: Evidence["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-1">No blockers are listed. This record still does not authorize worker start.</p>;
    return <div className="mt-2 rounded border border-amber-500/40 p-2" aria-label="Runtime design status">
        <p className="font-semibold">Runtime requirements remain incomplete</p>
        <p>{blockers.length} {blockers.length === 1 ? "requirement remains" : "requirements remain"} unavailable.</p>
        <details className="mt-1">
            <summary>Show what remains</summary>
            <ul aria-label="Runtime design blockers" className="mt-2 list-disc pl-5">
                {blockers.map((blocker) => <li key={blocker}>{workerBindingActivationBlockerLabel(blocker)}</li>)}
            </ul>
        </details>
    </div>;
}

function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
