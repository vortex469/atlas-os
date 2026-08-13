export type ProviderConnectionFieldKind =
    | "string"
    | "host"
    | "url"
    | "port"
    | "boolean"
    | "select"
    | "secret"
    | "path";

export type ProviderConnectionSecretState = "configured" | "missing";
export type ProviderConnectionTestStatus = "success" | "failure" | "degraded";

export type ProviderConnectionFieldOption = {
    value: string;
    label: string;
    description: string;
};

export type ProviderConnectionField = {
    key: string;
    label: string;
    kind: ProviderConnectionFieldKind;
    required: boolean;
    editable: boolean;
    secret: boolean;
    current_value: string | number | boolean | null;
    secret_state: ProviderConnectionSecretState | null;
    source: string | null;
    help_text: string;
    options: ProviderConnectionFieldOption[];
    validation: Record<string, unknown>;
};

export type ProviderConnectionSchema = {
    provider_id: string;
    provider_name: string;
    fields: ProviderConnectionField[];
    editable: boolean;
    testable: boolean;
    updated_at: string | null;
    metadata: Record<string, unknown>;
};

export type TestProviderConnectionRequest = {
    values: Record<string, unknown>;
    confirmed: boolean;
};

export type TestProviderConnectionResult = {
    provider_id: string;
    status: ProviderConnectionTestStatus;
    message: string;
    tested_at: string;
    latency_ms: number | null;
    diagnostics: Record<string, unknown>;
};

export type UpdateProviderConnectionRequest = {
    values: Record<string, unknown>;
    confirmed: boolean;
};

export type UpdateProviderConnectionResult = {
    provider_id: string;
    connection_schema: ProviderConnectionSchema;
    updated_at: string;
    message: string;
};
