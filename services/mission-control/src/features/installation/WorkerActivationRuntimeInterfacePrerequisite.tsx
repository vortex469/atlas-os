import type { WorkerActivationRuntimePlanReview } from "../../types/workerActivationRuntimePlanReview";
import { useWorkerActivationRuntimeInterfacePrerequisite } from "../../hooks/useWorkerActivationRuntimeInterfacePrerequisite";

export function WorkerActivationRuntimeInterfacePrerequisite({ review }: { review: WorkerActivationRuntimePlanReview }) {
    return <InventoryReader key={JSON.stringify(review)} review={review} />;
}

function InventoryReader({ review }: { review: WorkerActivationRuntimePlanReview }) {
    const state = useWorkerActivationRuntimeInterfacePrerequisite(review);
    return <section aria-label="Worker runtime interface prerequisite state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Worker runtime interface state</h6>
        <p>Worker start and execution remain blocked. Runtime prerequisites remain incomplete.</p>
        <p>Mission Control only displays Core evidence.</p>
        {state === "loading" && <p role="status">Loading interface prerequisite state...</p>}
        {state === "missing" && <p role="status">Core has no recorded interface prerequisite evidence for this review.</p>}
        {state === "unavailable" && <p role="status">Interface prerequisite inventory evidence is unavailable. No runtime outcome can be confirmed.</p>}
        {typeof state === "object" && <>
            <p>Core recorded an interface prerequisite inventory for this review.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this interface prerequisite evidence has expired." : "Core reports this interface prerequisite evidence is active."}</p>
            <p>Recording this inventory does not satisfy prerequisites, define a runtime interface, or authorize contact or worker start.</p>
            <p>This is the state at Core’s last evaluation.</p>
            <details className="mt-3">
                <summary>Advanced Core evidence</summary>
                <p>v0.59 retains the Core-owned v0.57 interface prerequisite inventory hardened in v0.58. Separate interface admission and definition-review stages are deferred.</p>
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
