export type ServiceStatus =
    | "online"
    | "offline"
    | "healthy"
    | "degraded"
    | "warning"
    | "critical"
    | "unknown";

export type ServiceHealth = {
    status: ServiceStatus | string;
    critical: boolean;
    url: string;
    latency_ms: number | null;
    http_status: number | null;
};

export type AtlasHealth = {
    atlas: ServiceStatus | string;
    services: Record<string, ServiceHealth>;
};
