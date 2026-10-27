import type { DeploymentAnalysisResponse } from "../features/forge/types";

export class DeploymentAnalysisResponseError extends Error {
    constructor() {
        super("The analysis report is incomplete or unreadable. Analyze the document again.");
        this.name = "DeploymentAnalysisResponseError";
    }
}

function requireReadable(condition: unknown): asserts condition {
    if (!condition) throw new DeploymentAnalysisResponseError();
}
function record(value: unknown): Record<string, unknown> {
    requireReadable(value !== null && typeof value === "object" && !Array.isArray(value));
    return value as Record<string, unknown>;
}
function rows(value: unknown): Record<string, unknown>[] {
    requireReadable(Array.isArray(value));
    return value.map(record);
}
function text(value: unknown): value is string {
    return typeof value === "string" && value.trim().length > 0;
}
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): value is number {
    return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum;
}

// Check fields used by Forge's view, preserving additive data and readable future
// labels. This is a display guard, not deployment validation or approval.
export function parseDeploymentAnalysisResponse(value: unknown): DeploymentAnalysisResponse {
    const result = record(record(value).result);
    const analysis = record(result.analysis);
    const plan = record(analysis.plan);
    const proposal = record(record(result.planning).proposal);
    requireReadable(text(analysis.analyzer) && text(plan.name) && text(plan.risk));

    const components = rows(plan.components);
    for (const component of components) {
        requireReadable(text(component.id) && text(component.name) && text(component.kind));
        for (const port of rows(component.ports)) {
            requireReadable(integer(port.container_port, 1, 65535)
                && (port.host_port === null || integer(port.host_port, 1, 65535))
                && text(port.protocol) && typeof port.public === "boolean");
        }
    }
    requireReadable(new Set(components.map(component => component.id)).size === components.length);
    for (const diagnostic of rows(analysis.diagnostics)) {
        requireReadable(text(diagnostic.code) && typeof diagnostic.message === "string"
            && (diagnostic.component_id === null || typeof diagnostic.component_id === "string"));
    }

    requireReadable(text(proposal.summary) && text(proposal.risk)
        && typeof proposal.approval_required === "boolean"
        && (proposal.estimated_duration_minutes === null || integer(proposal.estimated_duration_minutes)));
    const steps = rows(proposal.steps);
    for (const step of steps) {
        requireReadable(text(step.id) && integer(step.order, 1) && text(step.title) && typeof step.description === "string");
    }
    requireReadable(new Set(steps.map(step => step.id)).size === steps.length
        && new Set(steps.map(step => step.order)).size === steps.length);
    return value as DeploymentAnalysisResponse;
}
