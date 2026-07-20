export type DeploymentRisk =
    | "low"
    | "medium"
    | "high"
    | "critical";

export type DiagnosticSeverity =
    | "info"
    | "warning"
    | "critical";

export type PortBinding = {
    container_port: number;
    host_port: number | null;
    protocol: string;
    public: boolean;
};

export type ApplicationComponent = {
    id: string;
    name: string;
    kind: string;
    image: string | null;
    ports: PortBinding[];
};

export type Diagnostic = {
    code: string;
    severity: DiagnosticSeverity;
    message: string;
    component_id: string | null;
    recommendation?: string | null;
};

export type PlanningStep = {
    id: string;
    order: number;
    kind: string;
    title: string;
    description: string;
    component_id: string | null;
    provider_hint: string | null;
    requires_confirmation: boolean;
    destructive: boolean;
    estimated_duration_minutes: number | null;
};

export type DeploymentAnalysisResponse = {
    result: {
        analysis: {
            analyzer: string;
            plan: {
                id: string;
                name: string;
                source: string;
                components: ApplicationComponent[];
                risk: DeploymentRisk;
                requires_approval: boolean;
            };
            diagnostics: Diagnostic[];
            elapsed_ms: number;
        };
        planning: {
            planner: string;
            proposal: {
                id: string;
                summary: string;
                steps: PlanningStep[];
                risk: DeploymentRisk;
                approval_required: boolean;
                rollback_supported: boolean;
                estimated_duration_minutes: number | null;
            };
            warnings: string[];
            elapsed_ms: number;
        };
    };
};