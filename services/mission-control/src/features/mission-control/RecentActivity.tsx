import { Link } from "react-router-dom";
import { detailPath, record, rows, safeText, timestamp } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

// A view of Core's returned history only; fetching and freshness belong to the
// shared evidence hook. No local history is accumulated between snapshots.
export function RecentActivity({ evidence, loading = false }: { evidence?: Evidence; loading?: boolean }) {
    const page = record(evidence?.data);
    const returned = rows(page.items);
    const inspectable = returned.filter(event => detailPath("/operations/actions", event.id)
        && typeof event.id === "string" && event.id.trim().length > 0
        && typeof event.action_label === "string" && event.action_label.trim().length > 0);
    const incomplete = inspectable.length !== returned.length || inspectable.some(event =>
        !timestamp(event.completed_at) || (event.status !== "failed" && event.status !== "succeeded"));
    // Preserve the first source record for a repeated ID; never synthesize an
    // outcome by merging fields or treating unknown outcomes as successful.
    const unique = new Map<unknown, Record<string, unknown>>();
    for (const event of inspectable) if (!unique.has(event.id)) unique.set(event.id, event);
    const activity = [...unique.values()].sort((a, b) =>
        (timestamp(b.completed_at)?.getTime() ?? 0) - (timestamp(a.completed_at)?.getTime() ?? 0));
    return <>
        <p>Past provider actions and their recorded results. These do not show current system health or alerts.</p>
        {evidence?.stale && <p role="status">Refresh failed. Showing the last available actions; current activity may have changed.</p>}
        {activity.length === 0 && <p>{Array.isArray(page.items)
            ? (returned.length === 0 && (page.total === undefined || page.total === 0) && (page.has_more === undefined || page.has_more === false) ? "No recent actions recorded." : "Some recent activity records could not be read.")
            : evidence?.unavailable ? "Recent activity could not be loaded."
                : evidence?.data === undefined && loading ? "Checking recent activity…"
                    : "Recent activity information is unavailable."}</p>}
        {activity.length > 0 && incomplete && <p>Some recent activity records could not be read.</p>}
        <ol className="grid gap-3 md:grid-cols-2">{activity.slice(0, 5).map(event => {
            const date = timestamp(event.completed_at);
            const outcome = event.status === "failed" ? "Failed" : event.status === "succeeded" ? "Succeeded" : "Outcome unknown";
            const message = safeText(event.message);
            return <li key={String(event.id)} className="min-w-0 rounded-lg border border-mc-border-subtle p-3">
                <p className="font-medium">{outcome} · {safeText(event.action_label)}</p>
                <p className="mt-1 text-xs text-mc-text-muted">{safeText(event.provider_name) || "Provider unknown."}</p>
                {message && <p className="mt-2 text-sm">{message}</p>}
                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                    <Link to={detailPath("/operations/actions", event.id)!}>Inspect action →</Link>
                    {date ? <time dateTime={date.toISOString()} title={`UTC ${date.toISOString()}`} className="text-mc-text-muted">Completed {date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time> : <span className="text-mc-text-muted">Completion time unknown.</span>}
                </div>
            </li>;
        })}</ol>
        {activity.length > 5 && <p>Showing 5 of {activity.length} returned actions.</p>}
        <Link to="/operations/history">Open operational history →</Link>
    </>;
}
