import type { ServiceHealth } from "../types/health";
import { HealthEvidence } from "./HealthEvidence";

type ServiceHealthCardProps = {
    name: string;
    health: ServiceHealth;
    onSelect: () => void;
};

function formatLatency(latency: number | null): string {
    if (latency === null) {
        return "Unavailable";
    }

    return `${Math.round(latency)} ms`;
}

function formatHttpStatus(status: number | null): string {
    if (status === null) {
        return "No response";
    }

    return String(status);
}

export function ServiceHealthCard({
    name,
    health,
    onSelect,
}: ServiceHealthCardProps) {
    return (
        <button
            type="button"
            onClick={onSelect}
            className="mc-panel-interactive mc-focusable w-full p-5 text-left"
            aria-label={`View details for ${name}`}
        >
            <div className="flex flex-col items-start gap-4">
                <div>
                    <h3 className="font-semibold text-mc-text-primary">
                        {name}
                    </h3>
                    <p className="mt-1 text-xs uppercase tracking-wider text-mc-text-muted">
                        Service health
                    </p>
                </div>

                <HealthEvidence status={health.status} reason={health.message} />
            </div>

            <dl className="mc-divider mt-5 grid grid-cols-2 gap-4 border-t pt-4">
                <div>
                    <dt className="text-xs uppercase tracking-wider text-mc-text-muted">
                        Latency
                    </dt>
                    <dd className="mt-1 text-sm font-medium text-mc-text-secondary">
                        {formatLatency(health.latency_ms)}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-mc-text-muted">
                        HTTP
                    </dt>
                    <dd className="mt-1 text-sm font-medium text-mc-text-secondary">
                        {formatHttpStatus(health.http_status)}
                    </dd>
                </div>
            </dl>
        </button>
    );
}
