import { StatusBadge } from "./StatusBadge";

type ServiceCardProps = {
    name: string;
    status: string;
    critical?: boolean;
    latencyMs?: number | null;
    httpStatus?: number | null;
};

export function ServiceCard({
    name,
    status,
    critical = false,
    latencyMs,
    httpStatus,
}: ServiceCardProps) {
    return (
        <article className="group rounded-lg border border-slate-800 bg-slate-900 p-5 transition duration-200 hover:border-slate-700">
            <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                    <h3 className="truncate font-semibold text-slate-100">
                        {name}
                    </h3>

                    <p className="mt-1 text-xs uppercase tracking-wider text-slate-500">
                        {critical ? "Critical service" : "Supporting service"}
                    </p>
                </div>

                <StatusBadge status={status} />
            </div>

            <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-800 pt-4">
                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Latency
                    </dt>

                    <dd className="mt-1 text-sm font-medium text-slate-200">
                        {latencyMs === null || latencyMs === undefined
                            ? "—"
                            : `${latencyMs} ms`}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        HTTP
                    </dt>

                    <dd className="mt-1 text-sm font-medium text-slate-200">
                        {httpStatus ?? "—"}
                    </dd>
                </div>
            </dl>
        </article>
    );
}
