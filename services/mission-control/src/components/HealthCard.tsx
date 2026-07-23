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
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-8 shadow-sm">
            <div className="grid gap-8 md:grid-cols-[auto_1fr] md:items-center">
                <div>
                    <p className="text-sm font-medium text-slate-400">
                        Overall Health
                    </p>

                    <div className="mt-3 flex items-end gap-4">
                        <span className="text-6xl font-bold leading-none tracking-tight text-slate-100">
                            {score}
                        </span>

                        <div className="pb-1">
                            <StatusBadge status={status} />
                        </div>
                    </div>
                </div>

                <div className="md:border-l md:border-slate-800 md:pl-8">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Situation Report
                    </p>

                    <p className="mt-3 max-w-3xl text-left text-sm leading-6 text-slate-300">
                        {summary}
                    </p>
                </div>
            </div>
        </section>
    );
}