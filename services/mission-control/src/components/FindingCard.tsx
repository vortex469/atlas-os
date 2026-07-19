import { useState } from "react";

import type { AceFinding } from "../types/ace";

type FindingCardProps = {
    finding: AceFinding;
};

type SeverityStyle = {
    card: string;
    badge: string;
    dot: string;
};

type UnavailableEntity = {
    entity_id?: string;
    name?: string;
    state?: string;
};

const severityStyles: Record<string, SeverityStyle> = {
    info: {
        card: "border-slate-800",
        badge: "border-blue-500/30 bg-blue-500/10 text-blue-300",
        dot: "bg-blue-400",
    },
    warning: {
        card: "border-amber-500/25",
        badge: "border-amber-500/30 bg-amber-500/10 text-amber-300",
        dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.55)]",
    },
    critical: {
        card: "border-red-500/30",
        badge: "border-red-500/30 bg-red-500/10 text-red-300",
        dot: "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.65)]",
    },
};

function formatLabel(value: string): string {
    return value
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

function getUnavailableEntities(
    finding: AceFinding,
): UnavailableEntity[] {
    const value = finding.details.unavailable_entities;

    if (!Array.isArray(value)) {
        return [];
    }

    return value.filter(
        (entity): entity is UnavailableEntity =>
            typeof entity === "object" &&
            entity !== null,
    );
}

export function FindingCard({ finding }: FindingCardProps) {
    const [expanded, setExpanded] = useState(false);

    const normalizedSeverity = finding.severity.trim().toLowerCase();
    const style =
        severityStyles[normalizedSeverity] ??
        severityStyles.info;

    const unavailableEntities = getUnavailableEntities(finding);
    const visibleEntities = expanded
        ? unavailableEntities
        : unavailableEntities.slice(0, 5);

    return (
        <article
            className={[
                "rounded-lg border bg-slate-900 p-5",
                style.card,
            ].join(" ")}
        >
            <div className="flex items-start justify-between gap-5">
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <span
                            className={`h-2 w-2 rounded-full ${style.dot}`}
                            aria-hidden="true"
                        />

                        <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
                            {formatLabel(finding.source)}
                        </p>
                    </div>

                    <h3 className="mt-2 text-base font-semibold text-slate-100">
                        {finding.title}
                    </h3>
                </div>

                <span
                    className={[
                        "shrink-0 rounded-full border px-3 py-1",
                        "text-xs font-semibold uppercase tracking-wider",
                        style.badge,
                    ].join(" ")}
                >
                    {finding.severity}
                </span>
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-400">
                {finding.message}
            </p>

            <dl className="mt-5 grid grid-cols-3 gap-4 border-t border-slate-800 pt-4">
                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Category
                    </dt>

                    <dd className="mt-1 text-sm font-medium text-slate-200">
                        {formatLabel(finding.category)}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Health
                    </dt>

                    <dd className="mt-1 text-sm font-medium text-slate-200">
                        {finding.affects_health ? "Affected" : "Unaffected"}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Score Impact
                    </dt>

                    <dd
                        className={[
                            "mt-1 text-sm font-medium",
                            finding.score_penalty > 0
                                ? "text-amber-300"
                                : "text-slate-200",
                        ].join(" ")}
                    >
                        {finding.score_penalty > 0
                            ? `−${finding.score_penalty}`
                            : "None"}
                    </dd>
                </div>
            </dl>

            {unavailableEntities.length > 0 && (
                <div className="mt-5 border-t border-slate-800 pt-4">
                    <div className="flex items-center justify-between gap-4">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Unavailable Entities
                            </p>

                            <p className="mt-1 text-sm text-slate-400">
                                Showing {visibleEntities.length} of{" "}
                                {unavailableEntities.length}
                            </p>
                        </div>

                        <button
                            type="button"
                            onClick={() => setExpanded((current) => !current)}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:text-slate-100"
                        >
                            {expanded ? "Collapse" : "View details"}
                        </button>
                    </div>

                    <div className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1">
                        {visibleEntities.map((entity, index) => (
                            <div
                                key={`${entity.entity_id ?? "entity"}-${index}`}
                                className="flex items-center justify-between gap-4 rounded-md border border-slate-800 bg-slate-950/50 px-3 py-2"
                            >
                                <div className="min-w-0">
                                    <p className="truncate text-sm font-medium text-slate-200">
                                        {entity.name ??
                                            entity.entity_id ??
                                            "Unknown entity"}
                                    </p>

                                    {entity.entity_id && (
                                        <p className="truncate text-xs text-slate-500">
                                            {entity.entity_id}
                                        </p>
                                    )}
                                </div>

                                <span className="shrink-0 rounded-full border border-slate-700 bg-slate-800 px-2 py-1 text-xs uppercase text-slate-400">
                                    {entity.state ?? "unknown"}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </article>
    );
}
