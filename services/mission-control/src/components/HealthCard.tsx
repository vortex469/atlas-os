import { StatusBadge } from "./StatusBadge";

type HealthCardProps = {
    score: number;
    status: string;
    summary: string;
};

export function HealthCard({
    score,
    status,
    summary,
}: HealthCardProps) {
    return (
        <section className="mc-surface p-6 md:p-8">
            <div className="grid gap-8 md:grid-cols-[auto_1fr] md:items-center">
                <div>
                    <p className="text-sm font-medium text-mc-text-muted">
                        Overall Health
                    </p>

                    <div className="mt-3 flex items-end gap-4">
                        <span className="text-6xl font-bold leading-none tracking-tight text-mc-text-primary">
                            {score}
                        </span>

                        <div className="pb-1">
                            <StatusBadge status={status} />
                        </div>
                    </div>
                </div>

                <div className="md:border-l md:border-mc-divider md:pl-8">
                    <p className="text-xs font-semibold uppercase tracking-wider text-mc-text-muted">
                        Situation Report
                    </p>

                    <p className="mt-3 max-w-3xl text-left text-sm leading-6 text-mc-text-secondary">
                        {summary}
                    </p>
                </div>
            </div>
        </section>
    );
}
