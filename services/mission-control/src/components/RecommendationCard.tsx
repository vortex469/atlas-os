import type { AceRecommendation } from "../types/ace";

type RecommendationCardProps = {
    recommendation: AceRecommendation;
};

const priorityStyles: Record<string, string> = {
    low: "border-blue-500/30 bg-blue-500/10 text-blue-300",
    medium: "border-amber-500/30 bg-amber-500/10 text-amber-300",
    high: "border-orange-500/30 bg-orange-500/10 text-orange-300",
    critical: "border-red-500/30 bg-red-500/10 text-red-300",
};

function formatComponent(component: string | null): string {
    if (!component) {
        return "Atlas";
    }

    return component
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

export function RecommendationCard({
    recommendation,
}: RecommendationCardProps) {
    const normalizedPriority =
        recommendation.priority.trim().toLowerCase();

    const priorityClass =
        priorityStyles[normalizedPriority] ??
        "border-slate-600 bg-slate-800 text-slate-300";

    const confidence = Math.round(
        Math.max(0, Math.min(1, recommendation.confidence)) * 100,
    );

    return (
        <article className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-start justify-between gap-5">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
                        Recommended Action
                    </p>

                    <h3 className="mt-2 text-base font-semibold leading-6 text-slate-100">
                        {recommendation.title}
                    </h3>
                </div>

                <span
                    className={[
                        "shrink-0 rounded-full border px-3 py-1",
                        "text-xs font-semibold uppercase tracking-wider",
                        priorityClass,
                    ].join(" ")}
                >
                    {recommendation.priority}
                </span>
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-400">
                {recommendation.reason}
            </p>

            <dl className="mt-5 grid grid-cols-3 gap-4 border-t border-slate-800 pt-4">
                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Component
                    </dt>

                    <dd className="mt-1 text-sm font-medium text-slate-200">
                        {formatComponent(recommendation.component)}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Confidence
                    </dt>

                    <dd className="mt-1 text-sm font-medium text-slate-200">
                        {confidence}%
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Effort
                    </dt>

                    <dd className="mt-1 text-sm font-medium text-slate-200">
                        {recommendation.estimated_effort}
                    </dd>
                </div>
            </dl>
        </article>
    );
}
