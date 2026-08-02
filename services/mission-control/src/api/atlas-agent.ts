import axios, { isAxiosError } from "axios";

import type {
    CandidatePlanApiResponse,
    CandidatePlanningRequest,
    CandidatePlanningResponse,
    CandidateWorkflowRequest,
    CandidateWorkflowResponse,
    RepositoryStatus,
    ReviewReport,
    SprintStatus,
    VerificationReport,
    WorkflowDetailResponse,
    WorkflowImplementationApprovalResponse,
    WorkflowImplementationDecision,
    WorkflowListQuery,
    WorkflowListResponse,
    WorkflowVerificationApprovalResponse,
} from "../types/atlasAgent";

const ATLAS_AGENT_API_BASE_URL =
    import.meta.env.VITE_ATLAS_AGENT_API_BASE_URL ?? "/agent-api";

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
    try {
        const response = await atlasAgent.get<SprintStatus>(
            "/api/v1/agent/sprint",
        );

        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

export async function getVerificationReport(): Promise<VerificationReport | null> {
    try {
        const response = await atlasAgent.get<VerificationReport>(
            "/api/v1/agent/verification",
        );

        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

export async function getReviewReport(): Promise<ReviewReport | null> {
    try {
        const response = await atlasAgent.get<ReviewReport>(
            "/api/v1/agent/review",
        );

        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
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
