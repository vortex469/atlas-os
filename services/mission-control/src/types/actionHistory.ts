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
