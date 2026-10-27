import type { DeploymentAnalysisResponse } from "../features/forge/types";

export function deploymentAnalysisFixture(): DeploymentAnalysisResponse {
    return { result: {
        analysis: { analyzer: "fixture", elapsed_ms: 1, diagnostics: [{ code: "REVIEW_PORT", severity: "warning", message: "Review the reported port.", component_id: "web" }], plan: {
            id: "fixture-plan", name: "Compose preview", source: "compose", risk: "low", requires_approval: true,
            components: [{ id: "web", name: "Web", kind: "service", image: "example.invalid/fixture:one", ports: [{ container_port: 80, host_port: null, protocol: "tcp", public: false }] }],
        } },
        planning: { planner: "fixture", elapsed_ms: 1, warnings: [], proposal: {
            id: "fixture-proposal", summary: "Review this proposed plan.", risk: "low", approval_required: true,
            rollback_supported: false, estimated_duration_minutes: null,
            steps: [{ id: "review-step", order: 1, kind: "validate", title: "Review the service", description: "Review the proposed changes.", component_id: "web", provider_hint: null, requires_confirmation: true, destructive: false, estimated_duration_minutes: null }],
        } },
    } };
}

export function changedDeploymentAnalysis(path: string, value: unknown): unknown {
    const body = deploymentAnalysisFixture();
    const segments = path.split(".");
    let parent: unknown = body;
    for (const segment of segments.slice(0, -1)) parent = (parent as Record<string, unknown>)[segment];
    (parent as Record<string, unknown>)[segments.at(-1)!] = value;
    return body;
}
