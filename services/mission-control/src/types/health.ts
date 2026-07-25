export type ServiceStatus =
    | "online"
    | "offline"
    | "healthy"
    | "degraded"
    | "warning"
    | "critical"
    | "unknown";

export type ServiceHealth = {
    provider_id: string;
    status: ServiceStatus | string;
    latency_ms: number | null;
    http_status: number | null;
    message: string | null;
    details: Record<string, unknown>;
};

export type AtlasHealth = {
    atlas: ServiceStatus | string;
    services: Record<string, ServiceHealth>;
};
