export type ProviderActionParameters = Record<
    string,
    unknown
>;

export type ProviderAction = {
    id: string;
    label: string;
    description: string;
    icon: string;
    requires_confirmation: boolean;
    destructive: boolean;
    enabled: boolean;
    parameters: ProviderActionParameters;
};

export type ProviderActionRequest = {
    confirmed?: boolean;
    parameters?: ProviderActionParameters;
};

export type ProviderActionResult = {
    provider_id: string;
    action_id: string;
    status: "succeeded" | "failed";
    success: boolean;
    message: string;
    data: Record<string, unknown>;
    warnings: string[];
};

export type AtlasAPIErrorDetail = {
    code: string;
    message: string;
    status: number;
    details: Record<string, unknown>;
};

export type AtlasAPIError = {
    error: AtlasAPIErrorDetail;
    request_id: string;
};
