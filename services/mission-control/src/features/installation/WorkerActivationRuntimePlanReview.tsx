import { WorkerActivationRuntimeInterfacePrerequisite } from "./WorkerActivationRuntimeInterfacePrerequisite";
import type { WorkerActivationRuntimePlan } from "../../types/workerActivationRuntimePlan";
import { useWorkerActivationRuntimePlanReview } from "../../hooks/useWorkerActivationRuntimePlanReview";

export function WorkerActivationRuntimePlanReview({ plan }: { plan: WorkerActivationRuntimePlan }) {
    return <ReviewReader key={JSON.stringify(plan)} plan={plan} />;
}

function ReviewReader({ plan }: { plan: WorkerActivationRuntimePlan }) {
    const { state, retry } = useWorkerActivationRuntimePlanReview(plan);
    return <section aria-label="Worker runtime plan review state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Plan consistency review</h6>
        <p>This review checks a saved plan for consistency. It does not define, set up, or start a runtime; worker start and execution remain unavailable.</p>
        {state === "loading" && <p role="status">Checking the plan review…</p>}
        {state === "missing" && <p role="status">No consistency review has been saved for this plan.</p>}
        {state === "unavailable" && <div role="alert"><p>Atlas could not load the consistency review. Retry to check its status.</p><button type="button" onClick={retry} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {typeof state === "object" && <>
            <p>A consistency review is saved for this plan.</p>
            <p>{state.lifecycle === "expired" ? "This review has expired." : "This review is current."}</p>
            <details className="mt-3">
                <summary>Technical details</summary>
                <dl>{Object.entries({ "Plan review ID": state.runtimePlanReviewId, "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": formatUtcTimestamp(state.recordedAt), "Valid until": formatUtcTimestamp(state.validUntil), "Core evaluated at": formatUtcTimestamp(state.evaluatedAt), "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Core review findings">{JSON.stringify({ profile: state.profile, findings: state.findings }, null, 2)}</pre>
                <pre aria-label="Exact plan lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Review blockers</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.56 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimeInterfacePrerequisite review={state} />
        </>}
    </section>;
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
