export type ActionHistoryStatus = "succeeded" | "failed";

export type ProviderActionAuditEntry = {
    id: string;
    provider_id: string;
    provider_name: string;
    action_id: string;
    action_label: string;
    status: ActionHistoryStatus;
    success: boolean;
    message: string;
    confirmed: boolean;
    destructive: boolean;
    parameter_names: string[];
    request_id: string | null;
    started_at: string;
    completed_at: string;
    duration_ms: number;
};

export type ProviderActionHistorySummary = {
    entry_count: number;
    max_entries: number;
    retention_days: number;
    oldest_entry_at: string | null;
    newest_entry_at: string | null;
};

export type ProviderActionPruneResult = {
    deleted_entries: number;
    remaining_entries: number;
    cutoff: string;
};

export type ActionHistoryExportFormat = "json" | "csv";

export type ActionHistoryQuery = {
    limit?: number;
    status?: ActionHistoryStatus;
    providerId?: string;
    completedFrom?: string;
    completedTo?: string;
};

export type ProviderActionHistoryProvider = {
    id: string;
    name: string;
};
