import type { WorkerActivationRuntimePlanReview } from "../../types/workerActivationRuntimePlanReview";
import { useWorkerActivationRuntimeInterfacePrerequisite } from "../../hooks/useWorkerActivationRuntimeInterfacePrerequisite";

export function WorkerActivationRuntimeInterfacePrerequisite({ review }: { review: WorkerActivationRuntimePlanReview }) {
    return <InventoryReader review={review} />;
}

function InventoryReader({ review }: { review: WorkerActivationRuntimePlanReview }) {
    const { state, retry } = useWorkerActivationRuntimeInterfacePrerequisite(review);
    return <section aria-label="Worker runtime interface prerequisite state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Interface inventory review</h6>
        <p>Saving this inventory does not make a runtime ready, define its interface, contact a worker, or allow start.</p>
        {state === "loading" && <p role="status">Checking the interface inventory…</p>}
        {state === "missing" && <p role="status">No interface inventory has been saved for this review.</p>}
        {state === "unavailable" && <div role="alert"><p>Atlas could not load the interface inventory. Retry to check its status.</p><button type="button" onClick={retry} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry</button></div>}
        {typeof state === "object" && <>
            <p>An interface inventory is saved for this review.</p>
            <p>{state.lifecycle === "expired" ? "This inventory has expired." : "This inventory is current."}</p>
            <p>This status reflects the last Core check.</p>
            <details className="mt-3">
                <summary>Technical details</summary>
                <p>Runtime identity, capability, and lifecycle definition and review remain deferred; this inventory grants no runtime authority.</p>
                <dl>{Object.entries({ "Interface prerequisite inventory ID": state.runtimeInterfacePrerequisiteId, "Plan review ID": state.runtimePlanReviewId, "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": formatUtcTimestamp(state.recordedAt), "Valid until": formatUtcTimestamp(state.validUntil), "Core evaluated at": formatUtcTimestamp(state.evaluatedAt), "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Core interface prerequisite inventory">{JSON.stringify({ profile: state.profile, inventory: state.inventory }, null, 2)}</pre>
                <pre aria-label="Exact review lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Blockers</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.57 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
        </>}
    </section>;
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
