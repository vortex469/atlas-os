import axios, { isAxiosError } from "axios";

import type {
    CandidatePlanApiResponse,
    CandidatePlanningRequest,
    CandidatePlanningSuccessorRequest,
    CandidatePlanningResponse,
    CandidateImplementationTranslationRequest,
    CandidateImplementationTranslationResponse,
    CandidateWorkflowRequest,
    CandidateWorkflowResponse,
    WorkflowAuditResponse,
    RepositoryStatus,
    ReviewReport,
    SprintStatus,
    VerificationReport,
    WorkflowCommitApprovalResponse,
    WorkflowDetailResponse,
    WorkflowImplementationApprovalResponse,
    WorkflowImplementationDecision,
    WorkflowListQuery,
    WorkflowListResponse,
    WorkflowVerificationApprovalResponse,
} from "../types/atlasAgent";

const ATLAS_AGENT_API_BASE_URL =
    import.meta.env.VITE_ATLAS_AGENT_API_BASE_URL ?? "/agent-api";

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
    return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isVerificationCheck(value: unknown): boolean {
    if (!isRecord(value)) {
        return false;
    }

    return (
        typeof value.identifier === "string"
        && isStringArray(value.argv)
        && typeof value.working_directory === "string"
        && typeof value.status === "string"
        && (typeof value.return_code === "number" || value.return_code === null)
        && typeof value.stdout === "string"
        && typeof value.stderr === "string"
        && typeof value.duration_seconds === "number"
        && (typeof value.error === "string" || value.error === null)
    );
}

function isReviewFinding(value: unknown): boolean {
    if (!isRecord(value)) {
        return false;
    }

    return (
        typeof value.code === "string"
        && typeof value.category === "string"
        && typeof value.severity === "string"
        && typeof value.summary === "string"
        && typeof value.evidence === "string"
        && typeof value.recommendation === "string"
    );
}

function parseSprintStatus(value: unknown): SprintStatus {
    if (!isRecord(value)) {
        throw new Error("Malformed sprint status payload.");
    }

    if (
        typeof value.checkpoint_id === "string"
        && typeof value.title === "string"
        && typeof value.goal === "string"
        && typeof value.phase === "string"
    ) {
        return {
            checkpoint_id: value.checkpoint_id,
            title: value.title,
            goal: value.goal,
            phase: value.phase,
        };
    }

    throw new Error("Malformed sprint status payload.");
}

function parseVerificationReport(value: unknown): VerificationReport {
    if (!isRecord(value)) {
        throw new Error("Malformed verification report payload.");
    }

    if (
        typeof value.repository_root !== "string"
        || typeof value.status !== "string"
        || typeof value.duration_seconds !== "number"
        || !Array.isArray(value.results)
        || !value.results.every(isVerificationCheck)
    ) {
        throw new Error("Malformed verification report payload.");
    }

    return {
        repository_root: value.repository_root,
        status: value.status,
        duration_seconds: value.duration_seconds,
        results: value.results,
    } as VerificationReport;
}

function parseReviewReport(value: unknown): ReviewReport {
    if (!isRecord(value)) {
        throw new Error("Malformed review report payload.");
    }

    if (
        typeof value.request_id !== "string"
        || typeof value.checkpoint_id !== "string"
        || typeof value.status !== "string"
        || !isStringArray(value.recommendations)
        || !Array.isArray(value.findings)
        || !value.findings.every(isReviewFinding)
    ) {
        throw new Error("Malformed review report payload.");
    }

    return {
        request_id: value.request_id,
        checkpoint_id: value.checkpoint_id,
        status: value.status,
        recommendations: value.recommendations,
        findings: value.findings,
    } as ReviewReport;
}

async function getOptionalSummary<T>(
    request: () => Promise<{ data: unknown }>,
    parse: (payload: unknown) => T,
): Promise<T | null> {
    try {
        const response = await request();
        return parse(response.data);
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

export const atlasAgent = axios.create({
    baseURL: ATLAS_AGENT_API_BASE_URL,
    timeout: 15_000,
    headers: {
        Accept: "application/json",
    },
});

export async function getRepositoryStatus(): Promise<RepositoryStatus> {
    const response = await atlasAgent.get<RepositoryStatus>(
        "/api/v1/agent/repository",
    );

    return response.data;
}

export async function getSprintStatus(): Promise<SprintStatus | null> {
    return getOptionalSummary(
        () => atlasAgent.get<SprintStatus>("/api/v1/agent/sprint"),
        parseSprintStatus,
    );
}

export async function getVerificationReport(): Promise<VerificationReport | null> {
    return getOptionalSummary(
        () => atlasAgent.get<VerificationReport>("/api/v1/agent/verification"),
        parseVerificationReport,
    );
}

export async function getReviewReport(): Promise<ReviewReport | null> {
    return getOptionalSummary(
        () => atlasAgent.get<ReviewReport>("/api/v1/agent/review"),
        parseReviewReport,
    );
}

export async function createCandidatePlanningSession(
    request: CandidatePlanningRequest,
): Promise<CandidatePlanningResponse> {
    const response = await atlasAgent.post<CandidatePlanningResponse>(
        "/candidate-planning",
        request,
    );

    return response.data;
}

export async function getCandidatePlanningSession(
    sessionId: string,
): Promise<CandidatePlanningResponse | null> {
    try {
        const response = await atlasAgent.get<CandidatePlanningResponse>(
            `/candidate-planning/${encodeURIComponent(sessionId)}`,
        );

        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

export async function generateCandidatePlan(
    sessionId: string,
): Promise<CandidatePlanningResponse> {
    const response = await atlasAgent.post<CandidatePlanningResponse>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/plan`,
    );

    return response.data;
}

export async function getCandidatePlan(
    sessionId: string,
): Promise<CandidatePlanApiResponse | null> {
    try {
        const response = await atlasAgent.get<CandidatePlanApiResponse>(
            `/candidate-planning/${encodeURIComponent(sessionId)}/plan`,
        );

        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

export async function createSuccessorCandidatePlanningSession(
    sessionId: string,
    request?: CandidatePlanningSuccessorRequest,
): Promise<CandidatePlanningResponse> {
    const response = await atlasAgent.post<CandidatePlanningResponse>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/successor`,
        request,
    );

    return response.data;
}

export async function createCandidateWorkflowShell(
    sessionId: string,
    request?: CandidateWorkflowRequest,
): Promise<CandidateWorkflowResponse> {
    const response = await atlasAgent.post<CandidateWorkflowResponse>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/workflow`,
        request,
    );

    return response.data;
}

export async function createCandidateImplementationRequest(
    sessionId: string,
    request?: CandidateImplementationTranslationRequest,
): Promise<CandidateImplementationTranslationResponse> {
    const response = await atlasAgent.post<CandidateImplementationTranslationResponse>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/implementation`,
        request,
    );

    return response.data;
}

export async function getWorkflowDetail(
    workflowId: string,
): Promise<WorkflowDetailResponse | null> {
    try {
        const response = await atlasAgent.get<WorkflowDetailResponse>(
            `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/implementation-request`,
        );

        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

export async function getWorkflowAudit(
    workflowId: string,
): Promise<WorkflowAuditResponse | null> {
    try {
        const response = await atlasAgent.get<WorkflowAuditResponse>(
            `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/audit`,
        );

        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

export async function listWorkflows(
    query: WorkflowListQuery = {},
): Promise<WorkflowListResponse> {
    const params = Object.fromEntries(
        Object.entries(query).filter(([, value]) => value !== undefined && value !== ""),
    );
    const response = await atlasAgent.get<WorkflowListResponse>(
        "/api/v1/agent/workflows",
        { params },
    );

    return response.data;
}

export async function submitWorkflowImplementationApproval(
    workflowId: string,
    decision: WorkflowImplementationDecision,
): Promise<WorkflowImplementationApprovalResponse> {
    const response = await atlasAgent.post<WorkflowImplementationApprovalResponse>(
        `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/implementation-approval`,
        { workflow_id: workflowId, decision },
    );

    return response.data;
}

export async function submitWorkflowVerificationApproval(
    workflowId: string,
    decision: WorkflowImplementationDecision,
): Promise<WorkflowVerificationApprovalResponse> {
    const response = await atlasAgent.post<WorkflowVerificationApprovalResponse>(
        `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/verification-approval`,
        { workflow_id: workflowId, decision },
    );

    return response.data;
}

export async function submitWorkflowCommitApproval(
    workflowId: string,
    decision: WorkflowImplementationDecision,
): Promise<WorkflowCommitApprovalResponse> {
    const response = await atlasAgent.post<WorkflowCommitApprovalResponse>(
        `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/commit-approval`,
        { workflow_id: workflowId, decision },
    );

    return response.data;
}

export async function resumeWorkflow(workflowId: string): Promise<void> {
    await atlasAgent.post<void>(
        `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/resume`,
    );
}

export function getAtlasAgentErrorMessage(
    error: unknown,
    fallback: string,
): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data as
            | { detail?: string }
            | undefined;

        return detail?.detail ?? error.message ?? fallback;
    }

    return error instanceof Error ? error.message : fallback;
}
