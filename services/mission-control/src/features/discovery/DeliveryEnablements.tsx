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
            .catch((requestError: unknown) => { if (current) setError(getAtlasErrorMessage(requestError, "Delivery enablement evidence is currently unavailable.")); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const review = async (id: string) => {
        setError(null);
        try { setReviewed(await getDeliveryEnablement(id)); }
        catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The enablement evidence record is unavailable or was not found.")); }
    };
    const create = async () => {
        if (!confirming || !csrfToken || creating) return;
        setCreating(true); setError(null);
        try {
            const value = await createDeliveryEnablement(confirming.create, csrfToken, deliveryEnablementIdempotencyKey());
            setRecords((current) => [value, ...current.filter((item) => item.record.enablement_id !== value.record.enablement_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "Durable operator enablement evidence could not be created.")); }
        finally { setCreating(false); }
    };
    const used = new Set(records.map((record) => record.record.preflight_id));
    const available = candidates.filter((candidate) => !used.has(candidate.create.preflight_id));

    return <section aria-labelledby="delivery-enablement-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="delivery-enablement-heading" className="font-semibold text-slate-100">Operator-controlled delivery enablement evidence</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">Operator enabled does not mean activated, sent, delivered, admitted, installed, or executed.</p>
        <p className="mt-1 text-sm text-slate-300">Default-off durable evidence only. This is not delivery, Agent invocation, transport registration, authentication material loading, dispatch, workflow or worker execution, installation, deployment, rollback, or provider, repository, in-guest, or other mutation authority.</p>
        <p className="mt-1 text-sm text-slate-400">Enablement inherits the exact preflight expiry and can remain fresh only for the unused portion of its 30-second maximum window. It cannot renew, refresh, extend, consume, or bypass no-replay.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant remains blocked, non-installable, and non-executable. No deployment artifact or execution path is introduced.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading operator delivery enablement evidence…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No operator delivery enablement evidence records.</p>}
        {!loading && !error && records.length > 0 && <ul aria-label="Operator delivery enablement evidence records" className="mt-4 space-y-3">{records.map((operation) => <li key={operation.record.enablement_id} className="rounded-md border border-slate-700 p-3">
            <p className="font-semibold text-slate-200">Enablement evidence · {operation.status.lifecycle}</p>
            <p className="mt-1 text-xs text-slate-400">Status: {operation.record.status_at_creation}; evidence only and non-sending.</p>
            <p className="mt-1 text-xs text-slate-400">Enabled {operation.record.enabled_at}; expires {operation.record.expires_at}.</p>
            <button type="button" onClick={() => void review(operation.record.enablement_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review durable enablement evidence</button>
        </li>)}</ul>}
        {!loading && available.map((candidate) => <div key={candidate.create.preflight_id} className="mt-4 rounded border border-amber-400/30 p-3">
            <p className="break-all text-xs text-slate-300">Exact preflight {candidate.create.preflight_id} · fingerprint {candidate.create.preflight_fingerprint.value}</p>
            {csrfToken ? <button type="button" onClick={() => setConfirming(candidate)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Enable exact delivery for later consideration only</button> : <p className="mt-2 text-xs text-slate-400">An authenticated operator session with mutation protection is required.</p>}
        </div>)}
        {confirming && <section aria-labelledby="delivery-enablement-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="delivery-enablement-confirmation" className="font-semibold text-amber-100">Create durable operator enablement evidence only</h6>
            <p className="mt-2 text-sm text-slate-200">Exact required confirmation: “{DELIVERY_ENABLEMENT_CONFIRMATION}”</p>
            <p className="mt-2 text-sm text-slate-300">This records bounded operator intent only. It performs no delivery, Agent call, transport registration, authentication material read, dispatch, execution, installation, deployment, rollback, or mutation.</p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Preflight ID" value={confirming.create.preflight_id} /><Value name="Preflight fingerprint" value={confirming.create.preflight_fingerprint.value} /><Value name="Delivery preparation ID" value={confirming.deliveryPreparationId} /><Value name="Preparation fingerprint" value={confirming.preparationFingerprint.value} /></dl>
            <div className="mt-3 flex gap-2"><button type="button" disabled={creating} onClick={() => void create()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm durable operator enablement evidence only</button><button type="button" disabled={creating} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {creating && <p role="status" className="mt-2 text-sm text-slate-400">Creating durable operator enablement evidence only…</p>}
        </section>}
        {reviewed && <EnablementDetails operation={reviewed} />}
    </section>;
}

function EnablementDetails({ operation }: { operation: DeliveryEnablementOperationV1 }) {
    const { record, status, audit_evidence: audit } = operation;
    return <section aria-labelledby="delivery-enablement-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="delivery-enablement-detail" className="font-semibold text-slate-100">Durable operator enablement evidence only</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">{status.lifecycle === "enabled" ? "Enabled for later consideration only; not activated, sent, or executable." : `${status.lifecycle}; terminal or unavailable and never delivery authority.`}</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Lifecycle" value={status.lifecycle} /><Value name="Status" value={record.status_at_creation} /><Value name="Observed at" value={status.observed_at} /><Value name="Enabled at" value={record.enabled_at} /><Value name="Expires at" value={record.expires_at} /><Value name="Freshness rule" value="inherits the preflight expiry; at most the remaining portion of 30 seconds; never extended" /><Value name="Ownership" value="authenticated operator-scoped; foreign records are indistinguishable from absence" /><Value name="Confirmation" value={record.confirmation} /><Value name="Statement" value={record.statement} /><Value name="Source" value={record.source} /><Value name="Enablement ID" value={record.enablement_id} /><Value name="Enablement fingerprint" value={record.enablement_fingerprint.value} /><Value name="Preflight ID" value={record.preflight_id} /><Value name="Preflight fingerprint" value={record.preflight_fingerprint.value} /><Value name="Delivery preparation ID" value={record.delivery_preparation_id} /><Value name="Preparation fingerprint" value={record.preparation_fingerprint.value} /></dl>
        <h6 className="mt-5 font-semibold text-slate-200">Exact v0.20–v0.29 linkage</h6>
        <dl aria-label="Exact v0.20 through v0.29 enablement linkage" className="mt-2 grid gap-3 text-sm sm:grid-cols-2">{Object.entries(record.linkage).map(([name, value]) => <Value key={name} name={name.replaceAll("_", " ")} value={typeof value === "string" ? value : value.value} />)}</dl>
        <h6 className="mt-5 font-semibold text-slate-200">Audit evidence</h6>
        <dl aria-label="Delivery enablement audit evidence" className="mt-2 grid gap-3 text-sm sm:grid-cols-2"><Value name="Audit lifecycle" value={audit.lifecycle} /><Value name="Audit status" value={audit.status} /><Value name="Audit provenance" value={audit.provenance} /><Value name="Audit confirmation" value={audit.confirmation} /><Value name="Evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Audit enabled at" value={audit.enabled_at} /><Value name="Audit expires at" value={audit.expires_at} /></dl>
        <dl aria-label="Fixed-false enablement authority flags" className="mt-4 grid gap-2 text-sm sm:grid-cols-2">{["Default enabled", "Agent contacted", "Credentials loaded", "Production transport registered", "Delivery activated", "Delivery sent", "Delivery authorized", "Execution admission granted", "Execution authorized", "Dispatch allowed", "Worker allowed", "Workflow allowed", "Installation allowed", "Deployment allowed", "Mutation allowed", "Replay allowed", "Execution attempted", "Mutation attempted"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        <p className="mt-3 text-sm text-slate-400">The permanent operator-scoped idempotency reservation permits only an exact retry returning the original record. Expiry never releases it; there is no replay, refresh, replacement, or downstream consumer.</p>
        <p className="mt-2 text-sm text-slate-400">Errors are closed and redacted. Mission Control displays no raw provider payload, credential, command, log, internal path, address, or other-operator identity.</p>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
