export const OPERATIONAL_INTENT_CREATE = "operational_intent:create" as const;

export type OperatorPrincipal = {
    operator_id: string;
    authenticated_at: string;
    permissions: string[];
    auth_method: "core_session";
};

export type OperatorSessionResponse = {
    authenticated: true;
    principal: OperatorPrincipal;
    expires_at: string;
};

export type OperatorSessionResult = {
    session: OperatorSessionResponse;
    csrfToken: string;
};
