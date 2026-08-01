export type ProviderExpectationOption = {
    value: string;
    label: string;
    description: string;
    terminal: boolean;
};

export type ProviderResourceExpectation = {
    value: string | null;
    label: string;
    state: "needs_review" | "configured" | "ignored" | "unsupported";
    allowed_values: ProviderExpectationOption[];
};

export type ProviderResource = {
    provider_id: string;
    resource_id: string;
    display_name: string;
    resource_type: string;
    current_state: string;
    expectation: ProviderResourceExpectation;
    configured: boolean;
    missing: boolean;
    needs_review: boolean;
    metadata: Record<string, unknown>;
};

export type ProviderResourceSummary = {
    total: number;
    configured: number;
    needs_review: number;
    missing: number;
    ignored: number;
    by_type: Record<string, number>;
    by_state: Record<string, number>;
};

export type ProviderResourceCollection = {
    provider_id: string;
    provider_name: string;
    refreshed_at: string;
    resources: ProviderResource[];
    summary: ProviderResourceSummary;
    metadata: Record<string, unknown>;
};

export type UpdateResourceExpectationResult = {
    provider_id: string;
    resource_id: string;
    expectation: ProviderResourceExpectation;
    updated_at: string;
};
