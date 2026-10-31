import { useEffect, useState } from "react";

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
    const [listError, setListError] = useState(false);
    const [reviewError, setReviewError] = useState(false);
    const [failedReviewId, setFailedReviewId] = useState<string | null>(null);
    const [createUncertain, setCreateUncertain] = useState(false);
    const [attemptedPreflights, setAttemptedPreflights] = useState<Set<string>>(() => new Set());
    const [listAttempt, setListAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listDeliveryEnablements()
            .then((page) => { if (current) { setRecords(page.enablements); setListError(false); setCreateUncertain(false); } })
            .catch(() => { if (current) setListError(true); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [listAttempt]);

    const review = async (id: string) => {
        setReviewError(false);
        setFailedReviewId(null);
        try { setReviewed(await getDeliveryEnablement(id)); }
        catch {
            setReviewError(true);
            setFailedReviewId(id);
        }
    };
    const create = async () => {
        if (!confirming || !csrfToken || creating) return;
        const preflightId = confirming.create.preflight_id;
        setAttemptedPreflights((current) => new Set(current).add(preflightId));
        setCreating(true); setCreateUncertain(false);
        try {
            const value = await createDeliveryEnablement(confirming.create, csrfToken, deliveryEnablementIdempotencyKey());
            setRecords((current) => [value, ...current.filter((item) => item.record.enablement_id !== value.record.enablement_id)]);
            setReviewed(value); setConfirming(null);
        } catch { setCreateUncertain(true); setConfirming(null); }
        finally { setCreating(false); }
    };
    const used = new Set(records.map((record) => record.record.preflight_id));
    const available = candidates.filter((candidate) => !used.has(candidate.create.preflight_id) && !attemptedPreflights.has(candidate.create.preflight_id));

    return <section aria-labelledby="delivery-enablement-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="delivery-enablement-heading" className="font-semibold text-slate-100">Delivery choices</h5>
        <p className="mt-1 text-sm text-slate-300">Record your choice to enable this exact delivery for later consideration. This does not send, install, or run anything.</p>
        <p className="mt-1 text-sm text-slate-400">A choice expires with its readiness check, within 30 seconds. It can’t be renewed.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant can’t be installed or run from Atlas yet.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading operator delivery enablement evidence…</p>}
        {!loading && listError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"><p>{createUncertain ? "Atlas couldn’t reload the records. The save is still uncertain. Try again to check; Atlas won’t repeat the request." : "Atlas couldn’t load saved delivery choices."}</p><button type="button" onClick={() => { setLoading(true); setListError(false); setListAttempt((attempt) => attempt + 1); }} className="mt-3 rounded border border-slate-500 px-3 py-1.5 font-semibold">Try again</button></div>}
        {createUncertain && !listError && <div role="alert" className="mt-4 rounded border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100"><p>Atlas couldn’t confirm whether it saved this choice. Reload the records to check; Atlas won’t repeat the request automatically.</p><button type="button" disabled={loading} onClick={() => { setLoading(true); setListAttempt((attempt) => attempt + 1); }} className="mt-3 rounded border border-amber-400/50 px-3 py-1.5 font-semibold disabled:opacity-50">Reload records</button></div>}
        {!loading && !listError && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No delivery choices have been saved.</p>}
        {!loading && !listError && records.length > 0 && <ul aria-label="Saved delivery choices" className="mt-4 space-y-3">{records.map((operation) => <li key={operation.record.enablement_id} className="rounded-md border border-slate-700 p-3">
            <p className="font-semibold text-slate-200">Delivery choice · {enablementStatusLabel(operation.status.lifecycle)}</p>
            <p className="mt-1 text-sm text-slate-400">Saved {formatUtcTimestamp(operation.record.enabled_at)} · Expires {formatUtcTimestamp(operation.record.expires_at)}</p>
            <p className="mt-1 text-sm text-slate-400">This choice did not send delivery or start work.</p>
            <button type="button" onClick={() => void review(operation.record.enablement_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review details</button>
        </li>)}</ul>}
        {!loading && !listError && available.map((candidate) => <div key={candidate.create.preflight_id} className="mt-4 rounded border border-amber-400/30 p-3">
            <p className="font-semibold text-slate-200">Ready for a delivery choice</p>
            <p className="mt-1 text-sm text-slate-400">Save your choice for later consideration. Nothing will be sent now.</p>
            {csrfToken ? <button type="button" onClick={() => setConfirming(candidate)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Choose enablement for later review</button> : <p className="mt-2 text-sm text-slate-400">Sign in as an Atlas operator to save a delivery choice.</p>}
        </div>)}
        {confirming && <section aria-labelledby="delivery-enablement-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="delivery-enablement-confirmation" className="font-semibold text-amber-100">Save this delivery choice?</h6>
            <p className="mt-2 text-sm text-slate-200">This records your choice for this exact delivery. It does not send, install, or run anything.</p>
            <p className="mt-2 rounded bg-slate-900/50 p-3 text-sm text-slate-200">Required confirmation: “{DELIVERY_ENABLEMENT_CONFIRMATION}”</p>
            <details className="mt-3 text-sm"><summary className="cursor-pointer text-slate-300">Review linked records</summary><dl className="mt-3 grid gap-3 sm:grid-cols-2"><Value name="Preflight ID" value={confirming.create.preflight_id} /><Value name="Preflight fingerprint" value={confirming.create.preflight_fingerprint.value} /><Value name="Delivery preparation ID" value={confirming.deliveryPreparationId} /><Value name="Preparation fingerprint" value={confirming.preparationFingerprint.value} /></dl></details>
            <div className="mt-3 flex gap-2"><button type="button" disabled={creating} onClick={() => void create()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm my choice</button><button type="button" disabled={creating} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {creating && <p role="status" className="mt-2 text-sm text-slate-400">Saving your delivery choice…</p>}
        </section>}
        {reviewError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"><p>Atlas couldn’t load this delivery choice.</p><button type="button" disabled={!failedReviewId} onClick={() => { if (failedReviewId) void review(failedReviewId); }} className="mt-3 rounded border border-slate-500 px-3 py-1.5 font-semibold">Try again</button></div>}
        {reviewed && <EnablementDetails operation={reviewed} />}
    </section>;
}

function EnablementDetails({ operation }: { operation: DeliveryEnablementOperationV1 }) {
    const { record, status, audit_evidence: audit } = operation;
    return <section aria-labelledby="delivery-enablement-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="delivery-enablement-detail" className="font-semibold text-slate-100">Delivery choice details</h6>
        <p className="mt-1 text-sm text-slate-300">{enablementSummary(status.lifecycle)}</p>
        <p className="mt-1 text-sm text-slate-400">Saved {formatUtcTimestamp(record.enabled_at)} · Expires {formatUtcTimestamp(record.expires_at)}</p>
        <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-slate-400">Technical details</summary>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2"><Value name="Lifecycle" value={status.lifecycle} /><Value name="Status" value={record.status_at_creation} /><Value name="Observed at" value={status.observed_at} /><Value name="Freshness rule" value="inherits the preflight expiry; at most the remaining portion of 30 seconds; never extended" /><Value name="Ownership" value="authenticated operator-scoped; foreign records are indistinguishable from absence" /><Value name="Confirmation" value={record.confirmation} /><Value name="Statement" value={record.statement} /><Value name="Source" value={record.source} /><Value name="Enablement ID" value={record.enablement_id} /><Value name="Enablement fingerprint" value={record.enablement_fingerprint.value} /><Value name="Preflight ID" value={record.preflight_id} /><Value name="Preflight fingerprint" value={record.preflight_fingerprint.value} /><Value name="Delivery preparation ID" value={record.delivery_preparation_id} /><Value name="Preparation fingerprint" value={record.preparation_fingerprint.value} /></dl>
            <h6 className="mt-4 font-semibold text-slate-200">Linked records</h6>
            <dl aria-label="Exact v0.20 through v0.29 enablement linkage" className="mt-2 grid gap-3 sm:grid-cols-2">{Object.entries(record.linkage).map(([name, value]) => <Value key={name} name={name.replaceAll("_", " ")} value={typeof value === "string" ? value : value.value} />)}</dl>
            <h6 className="mt-4 font-semibold text-slate-200">Audit details</h6>
            <dl aria-label="Delivery enablement audit evidence" className="mt-2 grid gap-3 sm:grid-cols-2"><Value name="Audit lifecycle" value={audit.lifecycle} /><Value name="Audit status" value={audit.status} /><Value name="Audit provenance" value={audit.provenance} /><Value name="Audit confirmation" value={audit.confirmation} /><Value name="Evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Audit enabled at" value={audit.enabled_at} /><Value name="Audit expires at" value={audit.expires_at} /></dl>
            <dl aria-label="Fixed-false enablement authority flags" className="mt-4 grid gap-2 sm:grid-cols-2">{["Default enabled", "Agent contacted", "Credentials loaded", "Production transport registered", "Delivery activated", "Delivery sent", "Delivery authorized", "Execution admission granted", "Execution authorized", "Dispatch allowed", "Worker allowed", "Workflow allowed", "Installation allowed", "Deployment allowed", "Mutation allowed", "Replay allowed", "Execution attempted", "Mutation attempted"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
            <p className="mt-3 text-slate-400">The saved choice expires with the readiness check. A retry can return only this same record; it cannot renew or send delivery.</p>
        </details>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }

function enablementStatusLabel(lifecycle: DeliveryEnablementOperationV1["status"]["lifecycle"]) {
    switch (lifecycle) {
        case "enabled": return "Enabled for later review";
        case "expired": return "Expired";
        case "unavailable": return "Status unavailable";
    }
}

function enablementSummary(lifecycle: DeliveryEnablementOperationV1["status"]["lifecycle"]) {
    switch (lifecycle) {
        case "enabled": return "Enabled for later consideration. This did not send delivery or start work.";
        case "expired": return "This choice has expired and can’t be renewed. No delivery was sent.";
        case "unavailable": return "Atlas couldn’t confirm the status of this choice. No delivery was sent.";
    }
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
