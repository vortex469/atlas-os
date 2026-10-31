import { useEffect, useState } from "react";

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
    const [listError, setListError] = useState(false);
    const [reviewError, setReviewError] = useState(false);
    const [failedReviewId, setFailedReviewId] = useState<string | null>(null);
    const [createUncertain, setCreateUncertain] = useState(false);
    const [attemptedPreparations, setAttemptedPreparations] = useState<Set<string>>(() => new Set());
    const [listAttempt, setListAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listDeliveryActivationPreflights()
            .then((page) => { if (current) { setRecords(page.preflights); setListError(false); setCreateUncertain(false); } })
            .catch(() => { if (current) setListError(true); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [listAttempt]);

    const review = async (id: string) => {
        setReviewError(false);
        setFailedReviewId(null);
        try { setReviewed(await getDeliveryActivationPreflight(id)); }
        catch {
            setReviewError(true);
            setFailedReviewId(id);
        }
    };
    const create = async () => {
        if (!confirming || !csrfToken || creating) return;
        const preparationId = confirming.delivery_preparation_id;
        setAttemptedPreparations((current) => new Set(current).add(preparationId));
        setCreating(true); setCreateUncertain(false);
        try {
            const value = await createDeliveryActivationPreflight(confirming, csrfToken, deliveryActivationPreflightIdempotencyKey());
            setRecords((current) => [value, ...current.filter((item) => item.result.preflight_id !== value.result.preflight_id)]);
            setReviewed(value); setConfirming(null);
        } catch { setCreateUncertain(true); setConfirming(null); }
        finally { setCreating(false); }
    };
    const used = new Set(records.map((record) => record.result.delivery_preparation_id));
    const available = preparations.filter((value) => !used.has(value.delivery_preparation_id) && !attemptedPreparations.has(value.delivery_preparation_id));

    return <section aria-labelledby="delivery-preflight-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="delivery-preflight-heading" className="font-semibold text-slate-100">Delivery readiness checks</h5>
        <p className="mt-1 text-sm text-slate-300">Check saved delivery setup details for a later review. This does not approve, enable, or send delivery.</p>
        <p className="mt-1 text-sm text-slate-400">Results expire after 30 seconds or when the saved setup expires, whichever comes first. They can’t be refreshed.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant isn’t available for installation through Atlas yet.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading delivery activation preflight evidence…</p>}
        {!loading && listError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"><p>{createUncertain ? "Atlas couldn’t reload the records. The check is still uncertain. Try again to check; Atlas won’t repeat the request." : "Atlas couldn’t load saved readiness checks."}</p><button type="button" onClick={() => { setLoading(true); setListError(false); setListAttempt((attempt) => attempt + 1); }} className="mt-3 rounded border border-slate-500 px-3 py-1.5 font-semibold">Try again</button></div>}
        {createUncertain && !listError && <div role="alert" className="mt-4 rounded border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100"><p>Atlas couldn’t confirm whether it saved this check. Reload the records to check; Atlas won’t repeat the request automatically.</p><button type="button" disabled={loading} onClick={() => { setLoading(true); setListAttempt((attempt) => attempt + 1); }} className="mt-3 rounded border border-amber-400/50 px-3 py-1.5 font-semibold disabled:opacity-50">Reload records</button></div>}
        {!loading && !listError && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No readiness checks have been saved.</p>}
        {!loading && !listError && records.length > 0 && <ul aria-label="Delivery readiness checks" className="mt-4 space-y-3">{records.map((record) => <li key={record.result.preflight_id} className="rounded-md border border-slate-700 p-3">
            <p className="font-semibold text-slate-200">Readiness check · {preflightStatusLabel(record.status.lifecycle)}</p>
            <p className="mt-1 text-sm text-slate-400">{preflightDecisionLabel(record.result.decision)} · Checked {formatUtcTimestamp(record.result.evaluated_at)} · Expires {formatUtcTimestamp(record.result.expires_at)}</p>
            <button type="button" onClick={() => void review(record.result.preflight_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review details</button>
        </li>)}</ul>}
        {!loading && !listError && available.map((preparation) => <div key={preparation.delivery_preparation_id} className="mt-4 rounded border border-amber-400/30 p-3">
            <p className="font-semibold text-slate-200">Saved delivery setup</p>
            <p className="mt-1 text-sm text-slate-400">Check its readiness for a later review. This won’t enable or send delivery.</p>
            {csrfToken ? <button type="button" onClick={() => setConfirming(preparation)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Check readiness</button> : <p className="mt-2 text-sm text-slate-400">Sign in as an Atlas operator to check readiness.</p>}
        </div>)}
        {confirming && <section aria-labelledby="delivery-preflight-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="delivery-preflight-confirmation" className="font-semibold text-amber-100">Check delivery readiness?</h6>
            <p className="mt-2 text-sm text-slate-200">Atlas will check this saved setup against the current prerequisites. The check does not approve, enable, or send delivery.</p>
            <details className="mt-3 text-sm"><summary className="cursor-pointer text-slate-300">Review setup details</summary><dl className="mt-3 grid gap-3 sm:grid-cols-2"><Value name="Delivery preparation ID" value={confirming.delivery_preparation_id} /><Value name="Preparation fingerprint" value={confirming.preparation_fingerprint.value} /></dl></details>
            <div className="mt-3 flex gap-2"><button type="button" disabled={creating} onClick={() => void create()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm readiness check</button><button type="button" disabled={creating} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {creating && <p role="status" className="mt-2 text-sm text-slate-400">Checking delivery readiness…</p>}
        </section>}
        {reviewError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"><p>Atlas couldn’t load this readiness check.</p><button type="button" disabled={!failedReviewId} onClick={() => { if (failedReviewId) void review(failedReviewId); }} className="mt-3 rounded border border-slate-500 px-3 py-1.5 font-semibold">Try again</button></div>}
        {reviewed && <PreflightDetails record={reviewed} />}
    </section>;
}

function PreflightDetails({ record }: { record: DeliveryActivationPreflightOperationV1 }) {
    const { result, status, audit_evidence: audit } = record;
    return <section aria-labelledby="delivery-preflight-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="delivery-preflight-detail" className="font-semibold text-slate-100">Readiness check details</h6>
        <p className="mt-1 text-sm text-slate-300">{preflightSummary(status.lifecycle)}</p>
        <p className="mt-1 text-sm text-slate-400">Checked {formatUtcTimestamp(result.evaluated_at)} · Expires {formatUtcTimestamp(result.expires_at)}</p>
        <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-slate-400">Technical details</summary>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2"><Value name="Lifecycle" value={status.lifecycle} /><Value name="Decision" value={result.decision} /><Value name="Reason codes" value={result.reason_codes.join(", ") || "none"} /><Value name="Observed at" value={status.observed_at} /><Value name="Freshness rule" value="expires at the earlier of preparation validity or evaluation + 30 seconds; never extended" /><Value name="Ownership" value="authenticated operator-scoped; foreign records are indistinguishable from absence" /><Value name="Statement" value={result.statement} /><Value name="Source" value={result.source} /><Value name="Preflight ID" value={result.preflight_id} /><Value name="Preflight fingerprint" value={result.preflight_fingerprint.value} /><Value name="Delivery preparation ID" value={result.delivery_preparation_id} /><Value name="Preparation fingerprint" value={result.preparation_fingerprint.value} /><Value name="Endpoint fingerprint" value={result.endpoint_fingerprint.value} /></dl>
            <h6 className="mt-4 font-semibold text-slate-200">Linked records</h6>
            <dl aria-label="Exact v0.20 through v0.28 linkage" className="mt-2 grid gap-3 sm:grid-cols-2">{Object.entries(result.linkage).map(([name, value]) => <Value key={name} name={name.replaceAll("_", " ")} value={typeof value === "string" ? value : value.value} />)}</dl>
            <h6 className="mt-4 font-semibold text-slate-200">Audit details</h6>
            <dl aria-label="Delivery preflight audit evidence" className="mt-2 grid gap-3 sm:grid-cols-2"><Value name="Audit lifecycle" value={audit.lifecycle} /><Value name="Audit provenance" value={audit.provenance} /><Value name="Evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Intake request ID" value={audit.intake_request_id} /><Value name="Delivery attempt ID" value={audit.delivery_attempt_id} /><Value name="Audit reason codes" value={audit.reason_codes.join(", ") || "none"} /></dl>
            <dl aria-label="Fixed-false preflight authority flags" className="mt-4 grid gap-2 sm:grid-cols-2">{["Default enabled", "Agent contacted", "Credentials loaded", "Production transport registered", "Delivery activated", "Delivery authorized", "Execution admission granted", "Execution authorized", "Worker allowed", "Mutation allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
            <p className="mt-3 text-slate-400">A retry can return only the same saved check. It cannot refresh this result, extend its expiry, replay it, or approve downstream work.</p>
        </details>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }

function preflightStatusLabel(lifecycle: DeliveryActivationPreflightOperationV1["status"]["lifecycle"]) {
    switch (lifecycle) {
        case "eligible": return "Ready for review";
        case "expired": return "Expired";
        case "ineligible": return "Needs attention";
        case "unavailable": return "Status unavailable";
    }
}

function preflightDecisionLabel(decision: DeliveryActivationPreflightOperationV1["result"]["decision"]) {
    return decision === "eligible_for_later_activation" ? "Ready for a separate review" : "Not ready";
}

function preflightSummary(lifecycle: DeliveryActivationPreflightOperationV1["status"]["lifecycle"]) {
    switch (lifecycle) {
        case "eligible": return "Ready for a separate delivery decision. This check did not approve, enable, or send delivery.";
        case "expired": return "This check has expired and can’t be refreshed. No delivery was sent.";
        case "ineligible": return "This setup needs attention before it can be considered. No delivery was sent.";
        case "unavailable": return "Atlas couldn’t confirm whether this setup is ready. No delivery was sent.";
    }
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
