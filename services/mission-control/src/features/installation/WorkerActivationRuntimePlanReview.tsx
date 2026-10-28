import { WorkerActivationRuntimeInterfacePrerequisite } from "./WorkerActivationRuntimeInterfacePrerequisite";
import type { WorkerActivationRuntimePlan } from "../../types/workerActivationRuntimePlan";
import type { WorkerActivationRuntimePlanReview as Evidence } from "../../types/workerActivationRuntimePlanReview";
import { useWorkerActivationRuntimePlanReview } from "../../hooks/useWorkerActivationRuntimePlanReview";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

export function WorkerActivationRuntimePlanReview({ plan }: { plan: WorkerActivationRuntimePlan }) {
    return <ReviewReader key={JSON.stringify(plan)} plan={plan} />;
}

function ReviewReader({ plan }: { plan: WorkerActivationRuntimePlan }) {
    const state = useWorkerActivationRuntimePlanReview(plan);
    return <section aria-label="Worker runtime plan review state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Runtime plan review</h6>
        <p>A review checks saved plan evidence only. It does not mean a runtime exists or is ready. Worker start and execution remain blocked.</p>
        {state === "loading" && <p role="status">Loading plan review...</p>}
        {state === "missing" && <p role="status">Core has no recorded plan review evidence for this plan.</p>}
        {state === "unavailable" && <p role="status">Plan review evidence is unavailable. Runtime status is unknown because Core could not provide it.</p>}
        {typeof state === "object" && <>
            <p className="mt-2 font-semibold">Core recorded a consistency review of the plan.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this plan review evidence has expired." : "Core reports this plan review evidence is current."}</p>
            <BlockerSummary blockers={state.blockers} />
            <p className="mt-2">Recorded <time dateTime={state.recordedAt}>{formatDateTime(state.recordedAt)}</time> · Expires <time dateTime={state.validUntil}>{formatDateTime(state.validUntil)}</time>.</p>
            <details className="mt-3">
                <summary>Technical evidence</summary>
                <dl>{Object.entries({ "Plan review ID": state.runtimePlanReviewId, "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Core review findings">{JSON.stringify({ profile: state.profile, findings: state.findings }, null, 2)}</pre>
                <pre aria-label="Exact plan lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.56 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimeInterfacePrerequisite review={state} />
        </>}
    </section>;
}

function BlockerSummary({ blockers }: { blockers: Evidence["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-2">No unresolved requirements are listed. This review still does not approve worker start.</p>;
    return <div className="mt-2 rounded border border-amber-500/40 p-2" aria-label="Runtime plan review status">
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
