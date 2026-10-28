import { WorkerActivationRuntimePlanReview } from "./WorkerActivationRuntimePlanReview";
import { useEffect, useState } from "react";
import { getWorkerActivationRuntimePlan } from "../../api/workerActivationRuntimePlan";
import type { WorkerActivationRuntimeAdmission } from "../../types/workerActivationRuntimeAdmission";
import type { WorkerActivationRuntimePlan as Evidence } from "../../types/workerActivationRuntimePlan";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

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
        <h6 className="font-semibold">Runtime plan</h6>
        <p>A plan is reference-only evidence. It does not mean a runtime exists or is ready; worker start and execution remain blocked.</p>
        {state === "loading" && <p role="status">Loading runtime plan...</p>}
        {state === "missing" && <p role="status">Core has no recorded runtime plan evidence for this admission.</p>}
        {state === "unavailable" && <p role="status">Runtime plan evidence is unavailable. Runtime status is unknown because Core could not provide it.</p>}
        {typeof state === "object" && <>
            <p className="mt-2 font-semibold">Core recorded a reference-only runtime plan.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this plan evidence has expired." : "Core reports this plan evidence is current."}</p>
            <BlockerSummary blockers={state.blockers} />
            <p className="mt-2">Recorded <time dateTime={state.recordedAt}>{formatDateTime(state.recordedAt)}</time> · Expires <time dateTime={state.validUntil}>{formatDateTime(state.validUntil)}</time>.</p>
            <details className="mt-3">
                <summary>Technical evidence</summary>
                <dl>{Object.entries({ "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Reference-only runtime design">{JSON.stringify(state.design, null, 2)}</pre>
                <pre aria-label="Exact admission lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.55 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimePlanReview plan={state} />
        </>}
    </section>;
}

function BlockerSummary({ blockers }: { blockers: Evidence["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-2">No unresolved requirements are listed. This plan still does not mean a runtime is ready to start work.</p>;
    return <div className="mt-2 rounded border border-amber-500/40 p-2" aria-label="Runtime plan status">
        <p className="font-semibold">Worker start remains blocked</p>
        <p>{blockers.length} runtime {blockers.length === 1 ? "requirement is" : "requirements are"} still unresolved.</p>
        <details className="mt-1">
            <summary>Show the unresolved requirements</summary>
            <ul aria-label="Runtime requirements still unresolved" className="mt-2 list-disc pl-5">
                {blockers.map((blocker) => <li key={blocker}>{workerBindingActivationBlockerLabel(blocker)}</li>)}
            </ul>
        </details>
    </div>;
}

function formatDateTime(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
