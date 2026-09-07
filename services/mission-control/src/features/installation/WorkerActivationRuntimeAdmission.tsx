import { useEffect, useState } from "react";
import { getWorkerActivationRuntimeAdmission } from "../../api/workerActivationRuntimeAdmission";
import type { WorkerActivationRuntimePrerequisite } from "../../types/workerActivationRuntimePrerequisite";
import type { WorkerActivationRuntimeAdmission as Evidence } from "../../types/workerActivationRuntimeAdmission";

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
        <h6 className="font-semibold">Worker runtime admission evidence</h6>
        <p>Runtime prerequisites remain incomplete. Worker start and execution remain blocked.</p>
        <p>Mission Control only displays Core evidence.</p>
        {state === "loading" && <p role="status">Loading runtime admission state...</p>}
        {state === "missing" && <p role="status">Core has no recorded runtime admission evidence for this prerequisite.</p>}
        {state === "unavailable" && <p role="status">Runtime admission evidence is unavailable. No runtime outcome can be confirmed.</p>}
        {typeof state === "object" && <>
            <p>Core recorded admission evidence for this prerequisite. This accepts evidence for future runtime design consideration.</p>
            <p>{state.lifecycle === "expired" ? "Core reports this admission evidence has expired." : "Core reports this admission evidence is active."}</p>
            <details className="mt-3">
                <summary>Advanced v0.54 evidence</summary>
                <dl>{Object.entries({ "Runtime admission ID": state.runtimeAdmissionId, "Prerequisite ID": state.prerequisiteId, "Admission ID": state.admissionId, "Candidate ID": state.candidateId, "Operator ID": state.operatorId, "Recorded at": state.recordedAt, "Valid until": state.validUntil, "Core evaluated at": state.evaluatedAt, "Exact duplicate": String(state.exactDuplicate), ...Object.fromEntries(Object.entries(state.fingerprints).map(([key, value]) => [`${key} fingerprint`, value.value])) }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                <pre aria-label="Exact prerequisite lineage">{JSON.stringify(state.lineage, null, 2)}</pre>
                <p>Core reason codes</p>
                <ol>{state.blockers.map((code) => <li key={code}><code>{code}</code></li>)}</ol>
                <dl aria-label="v0.54 fixed-false authority">{Object.entries(state.authority).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
            </details>
        </>}
    </section>;
}
