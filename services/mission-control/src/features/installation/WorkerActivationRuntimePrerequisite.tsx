import { WorkerActivationRuntimeAdmission } from "./WorkerActivationRuntimeAdmission";
import { useEffect, useState } from "react";
import { getWorkerActivationRuntimePrerequisite } from "../../api/workerActivationRuntimePrerequisite";
import type { ControlledWorkerQueueReceipt } from "../../types/controlledWorkerQueueReceipt";
import type { WorkerActivationRuntimePrerequisite as Evidence } from "../../types/workerActivationRuntimePrerequisite";
import { workerBindingActivationBlockerLabel } from "./workerBindingActivationBlockers";

export function WorkerActivationRuntimePrerequisite({ receipt }: { receipt: ControlledWorkerQueueReceipt }) {
    return <PrerequisiteReader key={JSON.stringify(receipt)} receipt={receipt} />;
}

function PrerequisiteReader({ receipt }: { receipt: ControlledWorkerQueueReceipt }) {
    const [state, setState] = useState<Evidence | "loading" | "missing" | "unavailable">("loading");
    useEffect(() => {
        let current = true;
        getWorkerActivationRuntimePrerequisite(receipt)
            .then((value) => { if (current) setState(value ?? "missing"); })
            .catch(() => { if (current) setState("unavailable"); });
        return () => { current = false; };
    }, [receipt]);
    return <section aria-label="Worker runtime prerequisite state" className="mt-3 rounded border border-slate-800 p-3 text-sm">
        <h6 className="font-semibold">Runtime readiness</h6>
        <p>Core records the remaining runtime requirements here. A record does not mean a runtime exists or is ready.</p>
        {state === "loading" && <p role="status">Loading runtime readiness...</p>}
        {state === "missing" && <p role="status">No runtime readiness record is available for this queue receipt.</p>}
        {state === "unavailable" && <p role="status">Runtime readiness is unavailable. No runtime status is confirmed.</p>}
        {typeof state === "object" && <>
            <p className="mt-2 font-semibold">Runtime prerequisite record saved</p>
            <p>Runtime readiness remains incomplete. Worker start and execution are blocked.</p>
            <p>{state.lifecycle === "expired" ? "This record has expired." : "This record is current."}</p>
            <BlockerSummary blockers={state.blockers} />
            <p className="mt-2">Recorded {formatDateTime(state.recordedAt)} · Expires {formatDateTime(state.validUntil)}.</p>
            <details className="mt-3">
                <summary>Advanced details</summary>
                <dl>{Object.entries({ "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <p>Blockers</p>
                <ol aria-label="Ordered runtime readiness blockers">{state.blockers.map((code) => <li key={code}>{workerBindingActivationBlockerLabel(code)} <code>{code}</code></li>)}</ol>
                <dl aria-label="v0.53 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
            <WorkerActivationRuntimeAdmission prerequisite={state} />
        </>}
    </section>;
}

function BlockerSummary({ blockers }: { blockers: Evidence["blockers"] }) {
    if (blockers.length === 0) return <p className="mt-1">No blockers are listed. The runtime still is not ready to start work.</p>;
    return <div className="mt-2 rounded border border-amber-500/40 p-2" aria-label="Runtime readiness status">
        <p className="font-semibold">Runtime readiness is incomplete</p>
        <p>{blockers.length} {blockers.length === 1 ? "requirement remains" : "requirements remain"} unavailable.</p>
        <details className="mt-1">
            <summary>Show what remains</summary>
            <ul aria-label="Runtime readiness blockers" className="mt-2 list-disc pl-5">
                {blockers.map((blocker) => <li key={blocker}>{workerBindingActivationBlockerLabel(blocker)}</li>)}
            </ul>
        </details>
    </div>;
}

function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
