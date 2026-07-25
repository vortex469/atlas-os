import { useState } from "react";
import { SectionHeader } from "../../components/SectionHeader";
import { ServiceDetailsDrawer } from "../../components/ServiceDetailsDrawer";
import { ServiceHealthCard } from "../../components/ServiceHealthCard";
import type { ServiceHealth } from "../../types/health";

type ServiceHealthSectionProps = {
    services: Record<string, ServiceHealth>;
};

type SelectedService = {
    name: string;
    health: ServiceHealth;
};

const statusPriority: Record<string, number> = {
    critical: 0,
    offline: 1,
    degraded: 2,
    warning: 3,
    unknown: 4,
    healthy: 5,
    online: 5,
};

export function ServiceHealthSection({
    services,
}: ServiceHealthSectionProps) {
    const [selectedService, setSelectedService] =
        useState<SelectedService | null>(null);

    const entries = Object.entries(services).sort(
        ([nameA, healthA], [nameB, healthB]) => {
            const priorityA =
                statusPriority[healthA.status.toLowerCase()] ?? 4;
            const priorityB =
                statusPriority[healthB.status.toLowerCase()] ?? 4;

            if (priorityA !== priorityB) {
                return priorityA - priorityB;
            }

            return nameA.localeCompare(nameB);
        },
    );

    if (entries.length === 0) {
        return null;
    }

    return (
        <>
            <section>
                <SectionHeader
                    title="Service Health"
                    description="Live reachability, response status, and latency for Atlas infrastructure. Select a service for more details."
                />

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {entries.map(([name, serviceHealth]) => (
                        <ServiceHealthCard
                            key={name}
                            name={name}
                            health={serviceHealth}
                            onSelect={() =>
                                setSelectedService({
                                    name,
                                    health: serviceHealth,
                                })
                            }
                        />
                    ))}
                </div>
            </section>

            {selectedService && (
                <ServiceDetailsDrawer
                    name={selectedService.name}
                    health={
                        services[selectedService.name] ??
                        selectedService.health
                    }
                    onClose={() => setSelectedService(null)}
                />
            )}
        </>
    );
}
