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
            .catch((requestError: unknown) => { if (current) setError(getAtlasErrorMessage(requestError, "Readiness check records are currently unavailable.")); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const review = async (id: string) => {
        setError(null);
        try { setReviewed(await getDeliveryActivationPreflight(id)); }
        catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The readiness check record is unavailable or was not found.")); }
    };
    const create = async () => {
        if (!confirming || !csrfToken || creating) return;
        setCreating(true); setError(null);
        try {
            const value = await createDeliveryActivationPreflight(confirming, csrfToken, deliveryActivationPreflightIdempotencyKey());
            setRecords((current) => [value, ...current.filter((item) => item.result.preflight_id !== value.result.preflight_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The readiness check could not be saved.")); }
        finally { setCreating(false); }
    };
    const used = new Set(records.map((record) => record.result.delivery_preparation_id));
    const available = preparations.filter((value) => !used.has(value.delivery_preparation_id));

    return <section aria-labelledby="delivery-preflight-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="delivery-preflight-heading" className="font-semibold text-slate-100">Delivery readiness checks</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">A readiness check does not turn delivery on.</p>
        <p className="mt-1 text-sm text-slate-300">Core checks a saved preparation against current evidence and saves the result. It does not contact Agent or send work.</p>
        <p className="mt-1 text-sm text-slate-400">Results expire after 30 seconds at most, or sooner if the saved preparation expires. An expired result cannot be refreshed or reused.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant remains blocked because its deployment artifact and required proof are missing.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading readiness checks…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No readiness checks saved yet.</p>}
        {!loading && !error && records.length > 0 && <ul aria-label="Saved delivery readiness checks" className="mt-4 space-y-3">{records.map((record) => <li key={record.result.preflight_id} className="rounded-md border border-slate-700 p-3">
            <p className="font-semibold text-slate-200">{preflightLifecycleLabel(record.status.lifecycle)} · Delivery remains off</p>
            <details className="mt-1 text-xs text-slate-400"><summary className="cursor-pointer">Check ID and time limit</summary>
                <p className="mt-1 break-all">Check ID: {record.result.preflight_id}</p>
                <p>Checked {record.result.evaluated_at}; expires {record.result.expires_at}</p>
            </details>
            <button type="button" aria-label={`Review readiness check ${record.result.preflight_id}`} onClick={() => void review(record.result.preflight_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review details</button>
        </li>)}</ul>}
        {!loading && available.map((preparation) => <div key={preparation.delivery_preparation_id} className="mt-4 rounded border border-amber-400/30 p-3">
            <p className="font-semibold text-slate-200">Saved preparation is ready for a readiness check</p>
            <details className="mt-1 text-xs text-slate-400"><summary className="cursor-pointer">Preparation ID and fingerprint</summary>
                <p className="mt-1 break-all">Preparation ID: {preparation.delivery_preparation_id}</p>
                <p className="break-all">Fingerprint: {preparation.preparation_fingerprint.value}</p>
            </details>
            {csrfToken ? <button type="button" onClick={() => setConfirming(preparation)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Check this preparation</button> : <p className="mt-2 text-xs text-slate-400">Sign in with a protected operator session to save a check.</p>}
        </div>)}
        {confirming && <section aria-labelledby="delivery-preflight-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="delivery-preflight-confirmation" className="font-semibold text-amber-100">Confirm this readiness check</h6>
            <p className="mt-2 text-sm text-slate-200">Core will check one saved preparation against current evidence and save the result. It will not turn delivery on, contact Agent, or send work.</p>
            <p className="mt-2 break-all text-sm font-semibold text-slate-200">Preparation ID: {confirming.delivery_preparation_id}</p>
            <details className="mt-3 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Verify preparation fingerprint</summary>
                <p className="mt-2 break-all">{confirming.preparation_fingerprint.value}</p>
            </details>
            <div className="mt-3 flex gap-2"><button type="button" disabled={creating} onClick={() => void create()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Save readiness check</button><button type="button" disabled={creating} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {creating && <p role="status" className="mt-2 text-sm text-slate-400">Saving readiness check…</p>}
        </section>}
        {reviewed && <PreflightDetails record={reviewed} />}
    </section>;
}

function PreflightDetails({ record }: { record: DeliveryActivationPreflightOperationV1 }) {
    const { result, status, audit_evidence: audit } = record;
    return <section aria-labelledby="delivery-preflight-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="delivery-preflight-detail" className="font-semibold text-slate-100">Readiness check details</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">{status.lifecycle === "eligible" ? "Current evidence passed this check for separate review. Delivery is still off." : `${preflightLifecycleLabel(status.lifecycle)}. Delivery is still off.`}</p>
        <p className="mt-1 text-sm text-slate-300">This result records what Core checked. It is not approval to send work.</p>
        <details className="mt-3 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Technical check details</summary>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Lifecycle code" value={status.lifecycle} /><Value name="Decision code" value={result.decision} /><Value name="Reason codes" value={result.reason_codes.join(", ") || "none"} /><Value name="Observed at" value={status.observed_at} /><Value name="Checked at" value={result.evaluated_at} /><Value name="Expires at" value={result.expires_at} /><Value name="Time limit" value="expires at the earlier of preparation validity or 30 seconds after the check; never extended" /><Value name="Ownership" value="authenticated operator-scoped; foreign records are indistinguishable from absence" /><Value name="Statement" value={result.statement} /><Value name="Source" value={result.source} /><Value name="Check ID" value={result.preflight_id} /><Value name="Check fingerprint" value={result.preflight_fingerprint.value} /><Value name="Preparation ID" value={result.delivery_preparation_id} /><Value name="Preparation fingerprint" value={result.preparation_fingerprint.value} /><Value name="Endpoint fingerprint" value={result.endpoint_fingerprint.value} /></dl>
        </details>
        <details className="mt-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Earlier evidence linked to this check</summary>
            <dl aria-label="Exact v0.20 through v0.28 linkage" className="mt-3 grid gap-3 text-sm sm:grid-cols-2">{Object.entries(result.linkage).map(([name, value]) => <Value key={name} name={name.replaceAll("_", " ")} value={typeof value === "string" ? value : value.value} />)}</dl>
        </details>
        <details className="mt-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Audit record</summary>
            <dl aria-label="Delivery preflight audit evidence" className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Audit lifecycle" value={audit.lifecycle} /><Value name="Audit source" value={audit.provenance} /><Value name="Evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Intake request ID" value={audit.intake_request_id} /><Value name="Delivery attempt ID" value={audit.delivery_attempt_id} /><Value name="Audit reason codes" value={audit.reason_codes.join(", ") || "none"} /></dl>
        </details>
        <details className="mt-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Authority flags</summary>
            <dl aria-label="Fixed-false preflight authority flags" className="mt-3 grid gap-2 text-sm sm:grid-cols-2">{["Default enabled", "Agent contacted", "Credentials loaded", "Production transport registered", "Delivery activated", "Delivery authorized", "Execution admission granted", "Execution authorized", "Worker allowed", "Mutation allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        </details>
        <p className="mt-2 text-sm text-slate-400">Saving the same check request returns its original result. It does not check the evidence again, extend the time limit, or allow another system to act.</p>
        <p className="mt-2 text-sm text-slate-400">Errors hide credentials, commands, internal paths, endpoint addresses, and other operators’ identities.</p>
    </section>;
}

function preflightLifecycleLabel(lifecycle: DeliveryActivationPreflightOperationV1["status"]["lifecycle"]): string {
    if (lifecycle === "eligible") return "Eligible for separate review";
    if (lifecycle === "ineligible") return "Not eligible";
    if (lifecycle === "expired") return "Expired";
    return "Unavailable";
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
