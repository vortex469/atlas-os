import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { detailPath, record, rows, safeText, timestamp } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

// A view of Core's returned history only; fetching and freshness belong to the
// shared evidence hook. No local history is accumulated between snapshots.
export function RecentActivity({ evidence }: { evidence?: Evidence }) {
    const [now, setNow] = useState(Date.now);
    useEffect(() => {
        const timer = window.setInterval(() => setNow(Date.now()), 30_000);
        return () => window.clearInterval(timer);
    }, []);
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
        <p>Recent persisted provider action outcomes. Historical results do not establish current subsystem health or a current alert.</p>
        {activity.length === 0 && <p>{Array.isArray(page.items)
            ? (returned.length === 0 && (page.total === undefined || page.total === 0) && (page.has_more === undefined || page.has_more === false) ? "No recent actions recorded." : "Activity evidence malformed or incomplete.")
            : "Activity evidence unknown."}</p>}
        {activity.length > 0 && incomplete && <p>Some activity records are malformed or incomplete.</p>}
        <ol className="space-y-3">{activity.slice(0, 5).map(event => {
            const date = timestamp(event.completed_at);
            return <li key={String(event.id)}>
                <p>{event.status === "failed" ? "Error" : event.status === "succeeded" ? "Informational" : "Unknown outcome"} · {safeText(event.action_label)}</p>
                <p>{safeText(event.provider_name) || "Provider unknown."}</p>
                <p>{safeText(event.message)}</p>
                <Link to={detailPath("/operations/actions", event.id)!}>Inspect action →</Link>
                {date ? <time dateTime={date.toISOString()}>{date.toISOString()}</time> : <p>Completion time unknown.</p>}
                <p>{date && now - date.getTime() > 300_000 ? "Historical evidence (older than 5 minutes)." : "Action history does not establish current health."}</p>
            </li>;
        })}</ol>
        {activity.length > 5 && <p>Showing 5 of {activity.length} returned actions.</p>}
        <Link to="/operations/history">Open operational history →</Link>
    </>;
}
