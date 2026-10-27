import type { ProviderMonitoringIntentSuggestionV1 } from "../types/providerManagement";

export function ProviderIntentSuggestionCard({
    suggestion,
    stale,
    unavailable = false,
    reviewed,
    onReview,
}: {
    suggestion: ProviderMonitoringIntentSuggestionV1;
    stale: boolean;
    unavailable?: boolean;
    reviewed: boolean;
    onReview: () => void;
}) {
    return (
        <article aria-labelledby={`suggestion-${suggestion.suggestion_id}`} className="mt-4 rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-4">
            <h4 id={`suggestion-${suggestion.suggestion_id}`} className="text-sm font-semibold text-cyan-100">Monitoring suggestion</h4>
            {unavailable ? (
                <p role="status" className="mt-2 text-sm text-amber-200">Current monitoring settings could not be checked. Reload them before reviewing this suggestion.</p>
            ) : stale ? (
                <p role="alert" className="mt-2 text-sm text-amber-200">
                    This suggestion no longer matches the resource or its monitoring settings. Refresh resources to review current suggestions.
                </p>
            ) : (
                <>
                    <dl className="mt-2 space-y-2 text-sm">
                        <div><dt className="text-slate-400">Suggested state</dt><dd className="font-medium text-slate-100">Running</dd></div>
                        <div><dt className="text-slate-400">Reason</dt><dd className="text-slate-200">The provider reported this virtual machine as running. No monitoring setting applies to it.</dd></div>
                        <div><dt className="text-slate-400">Source</dt><dd className="text-slate-200">Monitoring rule</dd></div>
                    </dl>
                    <button type="button" onClick={onReview} className="mt-3 rounded-lg border border-cyan-500/50 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-100">
                        Review suggestion
                    </button>
                    {reviewed && <p role="status" className="mt-2 text-xs text-cyan-200">Suggestion reviewed. Saving a setting is a separate step.</p>}
                </>
            )}
        </article>
    );
}
