import type { WorkerActivationRuntimePlanReview } from "../../types/workerActivationRuntimePlanReview";
import type { WorkerActivationRuntimeInterfacePrerequisite as Evidence } from "../../types/workerActivationRuntimeInterfacePrerequisite";
import { useWorkerActivationRuntimeInterfacePrerequisite } from "../../hooks/useWorkerActivationRuntimeInterfacePrerequisite";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

export function WorkerActivationRuntimeInterfacePrerequisite({ review }: { review: WorkerActivationRuntimePlanReview }) {
    return <InventoryReader review={review} />;
}

function InventoryReader({ review }: { review: WorkerActivationRuntimePlanReview }) {
    const state = useWorkerActivationRuntimeInterfacePrerequisite(review);
    return <section aria-label="Worker runtime interface prerequisite state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Runtime interface requirements</h6>
        <p>This inventory does not show that a runtime exists or is ready, define a runtime connection, or authorize contact. Worker start and execution remain blocked.</p>
        {state === "loading" && <p role="status">Loading runtime requirements...</p>}
        {state === "missing" && <p role="status">Core has no recorded interface prerequisite evidence for this review.</p>}
        {state === "unavailable" && <p role="status">Interface prerequisite inventory evidence is unavailable. Runtime status is unknown because Core could not provide it.</p>}
        {typeof state === "object" && <>
            <p className="mt-2 font-semibold">Core recorded an interface prerequisite inventory of unresolved runtime requirements.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this interface prerequisite evidence has expired." : "Core reports this inventory is current."}</p>
            <BlockerSummary blockers={state.blockers} />
            <p className="mt-2">Recorded <time dateTime={state.recordedAt}>{formatDateTime(state.recordedAt)}</time> · Expires <time dateTime={state.validUntil}>{formatDateTime(state.validUntil)}</time>.</p>
            <p>Core last checked these requirements on <time dateTime={state.evaluatedAt}>{formatDateTime(state.evaluatedAt)}</time>.</p>
            <p>Recording this inventory does not satisfy prerequisites, define a runtime interface, or authorize contact or worker start.</p>
            <details className="mt-3">
                <summary>Technical evidence</summary>
                <p>v0.63 retains the Core-owned v0.57 interface prerequisite inventory integrated through v0.62. Successor runtime identity, capability and lifecycle definition and presentation remain deferred; no new runtime authority is established.</p>
                <p>Interface prerequisite inventory is evidence; runtime prerequisites remain incomplete.</p>
                <dl>{Object.entries({ "Interface prerequisite inventory ID": state.runtimeInterfacePrerequisiteId, "Plan review ID": state.runtimePlanReviewId, "Runtime plan ID": state.runtimePlanId, "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Core interface prerequisite inventory">{JSON.stringify({ profile: state.profile, inventory: state.inventory }, null, 2)}</pre>
                <pre aria-label="Exact review lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.57 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
        </>}
    </section>;
}

function BlockerSummary({ blockers }: { blockers: Evidence["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-2">Core lists no unresolved requirements. This inventory still does not define a runtime connection or permit worker start.</p>;
    return <div className="mt-2 rounded border border-amber-500/40 p-2" aria-label="Runtime interface readiness">
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
