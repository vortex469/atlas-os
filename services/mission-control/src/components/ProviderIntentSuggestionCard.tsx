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
    const expectation = suggestion.suggested_expectation.charAt(0).toUpperCase()
        + suggestion.suggested_expectation.slice(1);

    return (
        <article aria-labelledby={`suggestion-${suggestion.suggestion_id}`} className="mt-4 rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-4">
            <h4 id={`suggestion-${suggestion.suggestion_id}`} className="text-sm font-semibold text-cyan-100">Atlas suggestion</h4>
            {stale ? (
                <p role="alert" className="mt-2 text-sm text-amber-200">
                    This suggestion no longer matches the VM or its monitoring setting. Refresh resources to check for an updated suggestion.
                </p>
            ) : (
                <>
                    <dl className="mt-2 space-y-2 text-sm">
                        <div><dt className="text-slate-400">Suggested monitoring</dt><dd className="font-medium text-slate-100">{expectation}</dd></div>
                        <div><dt className="text-slate-400">Why</dt><dd className="text-slate-200">Atlas observed this VM running and found no saved monitoring expectation.</dd></div>
                    </dl>
                    <button type="button" onClick={onReview} className="mt-3 rounded-lg border border-cyan-500/50 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-100">
                        Review suggestion
                    </button>
                    {reviewed && <p role="status" className="mt-2 text-xs text-cyan-200">Added to the form. Nothing has been saved.</p>}
                </>
            )}
        </article>
    );
}
