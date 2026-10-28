import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import { createDeliveryEnablement, deliveryEnablementIdempotencyKey, getDeliveryEnablement, listDeliveryEnablements } from "../../api/deliveryEnablement";
import type { ContractFingerprint } from "../../types/atlasAgent";
import type { DeliveryEnablementCreateV1, DeliveryEnablementOperationV1 } from "../../types/deliveryEnablement";
import { DELIVERY_ENABLEMENT_CONFIRMATION } from "../../types/deliveryEnablement";

export interface DeliveryEnablementCandidate {
    create: DeliveryEnablementCreateV1;
    deliveryPreparationId: string;
    preparationFingerprint: ContractFingerprint;
}

export function DeliveryEnablements({ candidates = [], csrfToken }: { candidates?: DeliveryEnablementCandidate[]; csrfToken: string | null }) {
    const [records, setRecords] = useState<DeliveryEnablementOperationV1[]>([]);
    const [reviewed, setReviewed] = useState<DeliveryEnablementOperationV1 | null>(null);
    const [confirming, setConfirming] = useState<DeliveryEnablementCandidate | null>(null);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let current = true;
        listDeliveryEnablements()
            .then((page) => { if (current) setRecords(page.enablements); })
            .catch((requestError: unknown) => { if (current) setError(getAtlasErrorMessage(requestError, "Saved operator choices are currently unavailable.")); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const review = async (id: string) => {
        setError(null);
        try { setReviewed(await getDeliveryEnablement(id)); }
        catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The saved choice is unavailable or was not found.")); }
    };
    const create = async () => {
        if (!confirming || !csrfToken || creating) return;
        setCreating(true); setError(null);
        try {
            const value = await createDeliveryEnablement(confirming.create, csrfToken, deliveryEnablementIdempotencyKey());
            setRecords((current) => [value, ...current.filter((item) => item.record.enablement_id !== value.record.enablement_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "Your choice could not be saved.")); }
        finally { setCreating(false); }
    };
    const used = new Set(records.map((record) => record.record.preflight_id));
    const available = candidates.filter((candidate) => !used.has(candidate.create.preflight_id));

    return <section aria-labelledby="delivery-enablement-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="delivery-enablement-heading" className="font-semibold text-slate-100">Your choices for later delivery review</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">Saving a choice does not turn delivery on.</p>
        <p className="mt-1 text-sm text-slate-300">It records that you want one exact delivery considered later. Nothing is sent to Agent, installed, or run.</p>
        <p className="mt-1 text-sm text-slate-400">The choice expires with its readiness check, within 30 seconds. It cannot be renewed or used to send work.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant remains blocked because its deployment artifact and required proof are missing.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading saved choices…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No choices saved yet.</p>}
        {!loading && !error && records.length > 0 && <ul aria-label="Saved choices for later delivery review" className="mt-4 space-y-3">{records.map((operation) => <li key={operation.record.enablement_id} className="rounded-md border border-slate-700 p-3">
            <p className="font-semibold text-slate-200">{enablementStatus(operation.status.lifecycle)} · Delivery remains off</p>
            <details className="mt-1 text-xs text-slate-400"><summary className="cursor-pointer">Record ID and expiry</summary>
                <p className="mt-1 break-all">Record ID: {operation.record.enablement_id}</p>
                <p>Saved {operation.record.enabled_at}; expires {operation.record.expires_at}</p>
            </details>
            <button type="button" aria-label={`Review saved choice ${operation.record.enablement_id}`} onClick={() => void review(operation.record.enablement_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review details</button>
        </li>)}</ul>}
        {!loading && available.map((candidate) => <div key={candidate.create.preflight_id} className="mt-4 rounded border border-amber-400/30 p-3">
            <p className="font-semibold text-slate-200">Readiness check is available for separate review</p>
            <details className="mt-1 text-xs text-slate-400"><summary className="cursor-pointer">Check ID and fingerprint</summary>
                <p className="mt-1 break-all">Check ID: {candidate.create.preflight_id}</p>
                <p className="break-all">Fingerprint: {candidate.create.preflight_fingerprint.value}</p>
            </details>
            {csrfToken ? <button type="button" onClick={() => setConfirming(candidate)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Save choice for later review</button> : <p className="mt-2 text-xs text-slate-400">Sign in with a protected operator session to save your choice.</p>}
        </div>)}
        {confirming && <section aria-labelledby="delivery-enablement-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="delivery-enablement-confirmation" className="font-semibold text-amber-100">Confirm this saved choice</h6>
            <p className="mt-2 text-sm text-slate-200">You are saving your choice for this exact delivery to be considered later. It will not send, install, or execute anything.</p>
            <p className="mt-3 text-sm text-slate-300">To save it, confirm: “{DELIVERY_ENABLEMENT_CONFIRMATION}”</p>
            <p className="mt-2 break-all text-sm font-semibold text-slate-200">Readiness check ID: {confirming.create.preflight_id}</p>
            <p className="mt-1 break-all text-sm text-slate-300">Delivery preparation ID: {confirming.deliveryPreparationId}</p>
            <details className="mt-3 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Verify readiness and preparation fingerprints</summary>
                <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Readiness check fingerprint" value={confirming.create.preflight_fingerprint.value} /><Value name="Preparation fingerprint" value={confirming.preparationFingerprint.value} /></dl>
            </details>
            <div className="mt-3 flex gap-2"><button type="button" disabled={creating} onClick={() => void create()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Save this choice</button><button type="button" disabled={creating} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {creating && <p role="status" className="mt-2 text-sm text-slate-400">Saving your choice…</p>}
        </section>}
        {reviewed && <EnablementDetails operation={reviewed} />}
    </section>;
}

function EnablementDetails({ operation }: { operation: DeliveryEnablementOperationV1 }) {
    const { record, status, audit_evidence: audit } = operation;
    return <section aria-labelledby="delivery-enablement-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="delivery-enablement-detail" className="font-semibold text-slate-100">Saved choice details</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">{status.lifecycle === "enabled" ? "Your choice is saved for later review. Delivery is still off." : `${enablementStatus(status.lifecycle)}. Delivery is still off.`}</p>
        <p className="mt-1 text-sm text-slate-300">This records your choice for one exact delivery. It does not send, install, or execute anything.</p>
        <details className="mt-3 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Choice and evidence details</summary>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Lifecycle code" value={status.lifecycle} /><Value name="Saved status code" value={record.status_at_creation} /><Value name="Observed at" value={status.observed_at} /><Value name="Saved at" value={record.enabled_at} /><Value name="Expires at" value={record.expires_at} /><Value name="Time limit" value="expires with the readiness check; never extended" /><Value name="Ownership" value="authenticated operator-scoped; foreign records are indistinguishable from absence" /><Value name="Confirmation" value={record.confirmation} /><Value name="Statement" value={record.statement} /><Value name="Source" value={record.source} /><Value name="Choice ID" value={record.enablement_id} /><Value name="Choice fingerprint" value={record.enablement_fingerprint.value} /><Value name="Readiness check ID" value={record.preflight_id} /><Value name="Readiness check fingerprint" value={record.preflight_fingerprint.value} /><Value name="Delivery preparation ID" value={record.delivery_preparation_id} /><Value name="Preparation fingerprint" value={record.preparation_fingerprint.value} /></dl>
        </details>
        <details className="mt-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Earlier evidence linked to this choice</summary>
            <dl aria-label="Exact v0.20 through v0.29 enablement linkage" className="mt-3 grid gap-3 text-sm sm:grid-cols-2">{Object.entries(record.linkage).map(([name, value]) => <Value key={name} name={name.replaceAll("_", " ")} value={typeof value === "string" ? value : value.value} />)}</dl>
        </details>
        <details className="mt-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Audit record</summary>
            <dl aria-label="Delivery enablement audit evidence" className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Audit lifecycle" value={audit.lifecycle} /><Value name="Audit status" value={audit.status} /><Value name="Audit source" value={audit.provenance} /><Value name="Audit confirmation" value={audit.confirmation} /><Value name="Evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Saved at" value={audit.enabled_at} /><Value name="Expires at" value={audit.expires_at} /></dl>
        </details>
        <details className="mt-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Authority flags</summary>
            <dl aria-label="Fixed-false enablement authority flags" className="mt-3 grid gap-2 text-sm sm:grid-cols-2">{["Default enabled", "Agent contacted", "Credentials loaded", "Production transport registered", "Delivery activated", "Delivery sent", "Delivery authorized", "Execution admission granted", "Execution authorized", "Dispatch allowed", "Worker allowed", "Workflow allowed", "Installation allowed", "Deployment allowed", "Mutation allowed", "Replay allowed", "Execution attempted", "Mutation attempted"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        </details>
        <p className="mt-2 text-sm text-slate-400">Saving the same choice again returns the original record. Expiry does not extend or reset it.</p>
        <p className="mt-2 text-sm text-slate-400">This record does not prove that Agent received work or that any action was attempted.</p>
    </section>;
}

function enablementStatus(lifecycle: DeliveryEnablementOperationV1["status"]["lifecycle"]): string {
    if (lifecycle === "enabled") return "Saved for later review";
    if (lifecycle === "expired") return "Expired";
    return "Unavailable";
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
