import type { WorkerActivationRuntimePlan } from "../../types/workerActivationRuntimePlan";
import { useWorkerActivationRuntimePlanReview } from "../../hooks/useWorkerActivationRuntimePlanReview";

export function WorkerActivationRuntimePlanReview({ plan }: { plan: WorkerActivationRuntimePlan }) {
    return <ReviewReader key={JSON.stringify(plan)} plan={plan} />;
}

function ReviewReader({ plan }: { plan: WorkerActivationRuntimePlan }) {
    const state = useWorkerActivationRuntimePlanReview(plan);
    return <section aria-label="Worker runtime plan review state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Worker runtime plan review evidence</h6>
        <p>Plan review is evidence; runtime prerequisites remain incomplete. Worker start and execution remain blocked.</p>
        <p>Mission Control only displays Core evidence.</p>
        {state === "loading" && <p role="status">Loading plan review state...</p>}
        {state === "missing" && <p role="status">Core has no recorded plan review evidence for this plan.</p>}
        {state === "unavailable" && <p role="status">Plan review evidence is unavailable. No runtime outcome can be confirmed.</p>}
        {typeof state === "object" && <>
            <p>Core recorded a consistency review for this plan.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this plan review evidence has expired." : "Core reports this plan review evidence is active."}</p>
            <details className="mt-3">
                <summary>Advanced v0.56 evidence</summary>
                <dl>{Object.entries({ "Plan review ID": state.runtimePlanReviewId, "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Core review findings">{JSON.stringify({ profile: state.profile, findings: state.findings }, null, 2)}</pre>
                <pre aria-label="Exact plan lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.56 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
        </>}
    </section>;
}
