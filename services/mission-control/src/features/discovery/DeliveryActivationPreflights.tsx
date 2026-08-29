import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import {
    createDeliveryActivationPreflight,
    deliveryActivationPreflightIdempotencyKey,
    getDeliveryActivationPreflight,
    listDeliveryActivationPreflights,
} from "../../api/deliveryActivationPreflight";
import type {
    DeliveryActivationPreflightCreateV1,
    DeliveryActivationPreflightOperationV1,
} from "../../types/deliveryActivationPreflight";

export function DeliveryActivationPreflights({ preparations = [], csrfToken }: { preparations?: DeliveryActivationPreflightCreateV1[]; csrfToken: string | null }) {
    const [records, setRecords] = useState<DeliveryActivationPreflightOperationV1[]>([]);
    const [reviewed, setReviewed] = useState<DeliveryActivationPreflightOperationV1 | null>(null);
    const [confirming, setConfirming] = useState<DeliveryActivationPreflightCreateV1 | null>(null);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let current = true;
        listDeliveryActivationPreflights()
            .then((page) => { if (current) setRecords(page.preflights); })
            .catch((requestError: unknown) => { if (current) setError(getAtlasErrorMessage(requestError, "Delivery activation preflight evidence is currently unavailable.")); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const review = async (id: string) => {
        setError(null);
        try { setReviewed(await getDeliveryActivationPreflight(id)); }
        catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The preflight evidence record is unavailable or was not found.")); }
    };
    const create = async () => {
        if (!confirming || !csrfToken || creating) return;
        setCreating(true); setError(null);
        try {
            const value = await createDeliveryActivationPreflight(confirming, csrfToken, deliveryActivationPreflightIdempotencyKey());
            setRecords((current) => [value, ...current.filter((item) => item.result.preflight_id !== value.result.preflight_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "Durable preflight evidence could not be created.")); }
        finally { setCreating(false); }
    };
    const used = new Set(records.map((record) => record.result.delivery_preparation_id));
    const available = preparations.filter((value) => !used.has(value.delivery_preparation_id));

    return <section aria-labelledby="delivery-preflight-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="delivery-preflight-heading" className="font-semibold text-slate-100">Delivery activation preflight evidence</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">Local evidence preflight only — this is not delivery activation.</p>
        <p className="mt-1 text-sm text-slate-300">Default-disabled and non-activating. Eligibility is temporary evidence, never approval or authority. Core does not invoke Agent, register transport, load authentication material, dispatch work, start a workflow or worker, install, execute, deploy, roll back, or mutate provider, repository, or in-guest state.</p>
        <p className="mt-1 text-sm text-slate-400">An eligible snapshot is fresh for at most 30 seconds and may expire sooner with its dormant preparation. Expiry is terminal; it cannot be renewed, refreshed, consumed, or replayed.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant remains blocked, non-installable, and non-executable. No deployment artifact or delivery path is introduced.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading delivery activation preflight evidence…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No delivery activation preflight evidence records.</p>}
        {!loading && !error && records.length > 0 && <ul aria-label="Delivery activation preflight evidence records" className="mt-4 space-y-3">{records.map((record) => <li key={record.result.preflight_id} className="rounded-md border border-slate-700 p-3">
            <p className="font-semibold text-slate-200">Preflight evidence · {record.status.lifecycle}</p>
            <p className="mt-1 text-xs text-slate-400">Decision: {record.result.decision}; still non-authorizing and non-activating.</p>
            <p className="mt-1 text-xs text-slate-400">Evaluated {record.result.evaluated_at}; expires {record.result.expires_at}.</p>
            <button type="button" onClick={() => void review(record.result.preflight_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review durable preflight evidence</button>
        </li>)}</ul>}
        {!loading && available.map((preparation) => <div key={preparation.delivery_preparation_id} className="mt-4 rounded border border-amber-400/30 p-3">
            <p className="break-all text-xs text-slate-300">Dormant preparation {preparation.delivery_preparation_id} · fingerprint {preparation.preparation_fingerprint.value}</p>
            {csrfToken ? <button type="button" onClick={() => setConfirming(preparation)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Create durable preflight evidence only</button> : <p className="mt-2 text-xs text-slate-400">An authenticated operator session with mutation protection is required.</p>}
        </div>)}
        {confirming && <section aria-labelledby="delivery-preflight-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="delivery-preflight-confirmation" className="font-semibold text-amber-100">Confirm creation of durable preflight evidence only</h6>
            <p className="mt-2 text-sm text-slate-200">This evaluates one exact operator-owned dormant preparation. It does not activate delivery, invoke Agent, send, dispatch, execute, install, deploy, or grant mutation authority.</p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Delivery preparation ID" value={confirming.delivery_preparation_id} /><Value name="Preparation fingerprint" value={confirming.preparation_fingerprint.value} /></dl>
            <div className="mt-3 flex gap-2"><button type="button" disabled={creating} onClick={() => void create()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm durable evidence creation only</button><button type="button" disabled={creating} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {creating && <p role="status" className="mt-2 text-sm text-slate-400">Creating durable preflight evidence only…</p>}
        </section>}
        {reviewed && <PreflightDetails record={reviewed} />}
    </section>;
}

function PreflightDetails({ record }: { record: DeliveryActivationPreflightOperationV1 }) {
    const { result, status, audit_evidence: audit } = record;
    return <section aria-labelledby="delivery-preflight-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="delivery-preflight-detail" className="font-semibold text-slate-100">Durable local preflight evidence</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">{status.lifecycle === "eligible" ? "Temporarily eligible for later, separately authorized consideration; not activated." : `${status.lifecycle}; terminal or unavailable and not activated.`}</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Lifecycle" value={status.lifecycle} /><Value name="Decision" value={result.decision} /><Value name="Reason codes" value={result.reason_codes.join(", ") || "none"} /><Value name="Observed at" value={status.observed_at} /><Value name="Evaluated at" value={result.evaluated_at} /><Value name="Expires at" value={result.expires_at} /><Value name="Freshness rule" value="expires at the earlier of preparation validity or evaluation + 30 seconds; never extended" /><Value name="Ownership" value="authenticated operator-scoped; foreign records are indistinguishable from absence" /><Value name="Statement" value={result.statement} /><Value name="Source" value={result.source} /><Value name="Preflight ID" value={result.preflight_id} /><Value name="Preflight fingerprint" value={result.preflight_fingerprint.value} /><Value name="Delivery preparation ID" value={result.delivery_preparation_id} /><Value name="Preparation fingerprint" value={result.preparation_fingerprint.value} /><Value name="Endpoint fingerprint" value={result.endpoint_fingerprint.value} /></dl>
        <h6 className="mt-5 font-semibold text-slate-200">Exact v0.20–v0.28 linkage</h6>
        <dl aria-label="Exact v0.20 through v0.28 linkage" className="mt-2 grid gap-3 text-sm sm:grid-cols-2">{Object.entries(result.linkage).map(([name, value]) => <Value key={name} name={name.replaceAll("_", " ")} value={typeof value === "string" ? value : value.value} />)}</dl>
        <h6 className="mt-5 font-semibold text-slate-200">Audit evidence</h6>
        <dl aria-label="Delivery preflight audit evidence" className="mt-2 grid gap-3 text-sm sm:grid-cols-2"><Value name="Audit lifecycle" value={audit.lifecycle} /><Value name="Audit provenance" value={audit.provenance} /><Value name="Evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Intake request ID" value={audit.intake_request_id} /><Value name="Delivery attempt ID" value={audit.delivery_attempt_id} /><Value name="Audit reason codes" value={audit.reason_codes.join(", ") || "none"} /></dl>
        <dl aria-label="Fixed-false preflight authority flags" className="mt-4 grid gap-2 text-sm sm:grid-cols-2">{["Default enabled", "Agent contacted", "Credentials loaded", "Production transport registered", "Delivery activated", "Delivery authorized", "Execution admission granted", "Execution authorized", "Worker allowed", "Mutation allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        <p className="mt-3 text-sm text-slate-400">The operator-scoped idempotency reservation allows only an exact retry returning the original evidence. It does not reread evidence, extend expiry, refresh eligibility, permit replay, or authorize any downstream consumer.</p>
        <p className="mt-2 text-sm text-slate-400">Errors are closed and redacted. Mission Control displays no raw provider payload, credential, command, log, internal path, endpoint address, or other-operator identity.</p>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
