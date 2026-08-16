import type { ProviderMonitoringIntentSuggestionV1 } from "../types/providerManagement";

export function ProviderIntentSuggestionCard({
    suggestion,
    stale,
    reviewed,
    onReview,
}: {
    suggestion: ProviderMonitoringIntentSuggestionV1;
    stale: boolean;
    reviewed: boolean;
    onReview: () => void;
}) {
    return (
        <article aria-labelledby={`suggestion-${suggestion.suggestion_id}`} className="mt-4 rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-4">
            <h4 id={`suggestion-${suggestion.suggestion_id}`} className="text-sm font-semibold text-cyan-100">Advisory suggestion</h4>
            {stale ? (
                <p role="alert" className="mt-2 text-sm text-amber-200">
                    This suggestion was created for a different resource incarnation or monitoring state and can no longer be applied.
                </p>
            ) : (
                <>
                    <dl className="mt-2 space-y-2 text-sm">
                        <div><dt className="text-slate-400">Suggested monitoring expectation</dt><dd className="font-medium text-slate-100">Running</dd></div>
                        <div><dt className="text-slate-400">Reason</dt><dd className="text-slate-200">This QEMU is currently observed running and has no active monitoring intent.</dd></div>
                        <div><dt className="text-slate-400">Source</dt><dd className="text-slate-200">Provider intelligence rule</dd></div>
                    </dl>
                    <button type="button" onClick={onReview} className="mt-3 rounded-lg border border-cyan-500/50 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-100">
                        Review suggestion
                    </button>
                    {reviewed && <p role="status" className="mt-2 text-xs text-cyan-200">Suggestion selected for local review. Save remains a separate explicit action.</p>}
                </>
            )}
        </article>
    );
}
