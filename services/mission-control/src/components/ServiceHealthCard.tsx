import type { ServiceHealth } from "../types/health";
import { HealthEvidence } from "./HealthEvidence";

type ServiceHealthCardProps = {
    name: string;
    health: ServiceHealth;
    onSelect: (trigger: HTMLButtonElement) => void;
};

export function ServiceHealthCard({
    name,
    health,
    onSelect,
}: ServiceHealthCardProps) {
    return (
        <button
            type="button"
            onClick={(event) => onSelect(event.currentTarget)}
            aria-haspopup="dialog"
            className="mc-panel-interactive mc-focusable w-full p-5 text-left"
            aria-label={`View details for ${name}`}
        >
            <div className="flex flex-col items-start gap-4">
                <div>
                    <h3 className="font-semibold text-mc-text-primary">
                        {name}
                    </h3>
                    <p className="mt-1 text-xs uppercase tracking-wider text-mc-text-muted">
                        Reachability from Atlas Core
                    </p>
                </div>

                <HealthEvidence
                    status={health.status}
                    reason={health.message}
                    unavailableLabel="Unreachable from Atlas Core"
                    compact
                />
            </div>

            <div className="mc-divider mt-5 flex items-center justify-between border-t pt-4 text-xs font-semibold text-mc-primary-strong">
                <span>View details</span>
                <span aria-hidden="true">→</span>
            </div>
        </button>
    );
}
