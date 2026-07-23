import type { ServiceStatus } from "./health";

export type ProviderHealthDetails = {
    url?: string | null;
    critical?: boolean | null;
    [key: string]: unknown;
};

export type ProviderHealth = {
    status: ServiceStatus | string;
    latency_ms: number | null;
    http_status: number | null;
    message: string | null;
    details: ProviderHealthDetails;
};

export type Provider = {
    id: string;
    name: string;
    workspace: string;
    priority: string;
    version: string;
    description: string;
    icon: string;
    capabilities: string[];
    health: ProviderHealth;
};
