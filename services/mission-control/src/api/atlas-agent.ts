import axios, { isAxiosError } from "axios";

import type {
    AgentInfo,
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
    WorkflowOperationalLifecycle,
    WorkflowRecoveryDiagnostic,
    OperationalSupportBundle,
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

function isNullableString(value: unknown): value is string | null {
    return value === null || typeof value === "string";
}

function isNullableDateTime(value: unknown): value is string | null {
    return value === null || (typeof value === "string" && Number.isFinite(Date.parse(value)));
}

function isNullableBoolean(value: unknown): value is boolean | null {
    return value === null || typeof value === "boolean";
}

function isOneOf(value: unknown, options: readonly string[]): value is string {
    return typeof value === "string" && options.includes(value);
}

function isNonNegativeSafeInteger(value: unknown): value is number {
    return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isSafeRouteId(value: unknown): value is string {
    if (typeof value !== "string" || !value.trim()) return false;
    try {
        encodeURIComponent(value);
        return true;
    } catch {
        return false;
    }
}

// TypeScript types do not validate JSON received from Atlas Agent at runtime.
function parseWorkflowListResponse(value: unknown): WorkflowListResponse {
    if (!isRecord(value) || Array.isArray(value) || !Array.isArray(value.items)
        || typeof value.total !== "number" || !Number.isSafeInteger(value.total) || value.total < 0
        || typeof value.limit !== "number" || !Number.isSafeInteger(value.limit) || value.limit <= 0
        || typeof value.offset !== "number" || !Number.isSafeInteger(value.offset) || value.offset < 0
        || value.total < value.items.length) {
        throw new Error("Malformed workflow list payload.");
    }

    const workflowIds = new Set<string>();
    const validItems = value.items.every((item) => {
        if (!isRecord(item) || Array.isArray(item)
            || !isSafeRouteId(item.workflow_id)
            || typeof item.workflow_source !== "string"
            || typeof item.workflow_state !== "string"
            || (item.effect_kind !== "repository_change" && item.effect_kind !== "operational_action")
            || !isNullableString(item.execution_intent)
            || !isNullableString(item.candidate_id)
            || !isNullableString(item.planning_session_id)
            || !isNullableString(item.repository)
            || !isNullableString(item.target_id)
            || typeof item.last_result_summary !== "string"
            || !Array.isArray(item.timeline)
            || !item.timeline.every((stage) => isRecord(stage) && !Array.isArray(stage)
                && typeof stage.name === "string"
                && typeof stage.status === "string")
            || workflowIds.has(item.workflow_id)) {
            return false;
        }

        workflowIds.add(item.workflow_id);
        return true;
    });
    if (!validItems) throw new Error("Malformed workflow list payload.");

    return value as unknown as WorkflowListResponse;
}

function isOperationalLifecycleApproval(value: unknown): boolean {
    if (value === null) return true;
    return isRecord(value) && !Array.isArray(value)
        && isNullableString(value.approval_id)
        && typeof value.decision_status === "string"
        && isOneOf(value.presentation_state, ["actionable", "historical", "expired", "superseded", "resolved"])
        && typeof value.actionable === "boolean"
        && isNullableDateTime(value.expires_at);
}

function parseWorkflowOperationalLifecycle(value: unknown): WorkflowOperationalLifecycle {
    if (!isRecord(value) || Array.isArray(value)
        || typeof value.applicable !== "boolean"
        || !isOneOf(value.availability, ["not_applicable", "agent_only", "complete", "unavailable"])
        || !isOneOf(value.consistency_status, ["not_applicable", "agent_only", "consistent", "core_unavailable", "mismatch"])
        || !isNullableString(value.controlled_reason)
        || !isSafeRouteId(value.workflow_id)
        || typeof value.workflow_state !== "string"
        || !isNullableString(value.agent_execution_stage)
        || !isNullableString(value.candidate_id)
        || !isNullableString(value.planning_session_id)
        || !isOneOf(value.effect_kind, ["repository_change", "operational_action"])
        || !isNullableString(value.execution_intent)
        || !isNullableString(value.provider_id)
        || !isNullableString(value.resource_id)
        || !isNullableString(value.resource_type)
        || !isNullableString(value.target_label)
        || !isNullableString(value.operator_intent_record_id)
        || !isNullableString(value.candidate_source_subsystem)
        || !isNullableString(value.candidate_fingerprint)
        || !isNullableString(value.plan_fingerprint)
        || !isOperationalLifecycleApproval(value.preparation_approval)
        || !isOperationalLifecycleApproval(value.action_approval)
        || !isNullableString(value.action_request_id)
        || !isNullableString(value.request_digest)
        || !isNullableString(value.target_fingerprint)
        || !isNullableString(value.target_version)
        || !isNullableString(value.disruption_scope)
        || !isNullableDateTime(value.request_created_at)
        || !isNullableDateTime(value.request_expires_at)
        || !isNullableString(value.core_record_state)
        || !Array.isArray(value.transitions)
        || !value.transitions.every((transition) => isRecord(transition) && !Array.isArray(transition)
            && isNonNegativeSafeInteger(transition.sequence)
            && typeof transition.state === "string"
            && isNullableDateTime(transition.occurred_at) && transition.occurred_at !== null)
        || typeof value.barrier_crossed !== "boolean"
        || !isNonNegativeSafeInteger(value.barrier_crossing_count)
        || typeof value.provider_operation_captured !== "boolean"
        || !isNonNegativeSafeInteger(value.provider_operation_capture_count)
        || !isNullableString(value.dispatch_status)
        || !isNullableString(value.provider_operation_reference)
        || !isNullableDateTime(value.dispatch_started_at)
        || !isNullableDateTime(value.dispatch_completed_at)
        || !isNullableString(value.verification_status)
        || !isNullableString(value.observed_target_fingerprint)
        || !isNullableString(value.observed_state)
        || !isNullableString(value.observed_health)
        || !isNullableDateTime(value.verification_started_at)
        || !isNullableDateTime(value.verification_completed_at)
        || !isNullableDateTime(value.verification_deadline)
        || typeof value.terminal !== "boolean") {
        throw new Error("Malformed operational lifecycle payload.");
    }

    return value as unknown as WorkflowOperationalLifecycle;
}

function parseWorkflowRecoveryDiagnostic(value: unknown): WorkflowRecoveryDiagnostic {
    if (!isRecord(value) || Array.isArray(value)
        || typeof value.applicable !== "boolean"
        || !isOneOf(value.diagnostic_status, ["healthy", "pending", "attention_required", "recovery_in_progress", "outcome_uncertain", "unavailable"])
        || !isOneOf(value.consistency, ["consistent", "agent_only", "core_unavailable", "immutable_mismatch", "transition_mismatch", "terminal_mismatch"])
        || !isRecord(value.correlation) || Array.isArray(value.correlation)
        || !isSafeRouteId(value.correlation.workflow_id)
        || !isNullableString(value.correlation.request_id)
        || !isNullableBoolean(value.correlation.request_digest_match)
        || typeof value.correlation.agent_record_present !== "boolean"
        || typeof value.correlation.core_record_present !== "boolean"
        || !isRecord(value.dispatch_evidence) || Array.isArray(value.dispatch_evidence)
        || typeof value.dispatch_evidence.barrier_crossed !== "boolean"
        || typeof value.dispatch_evidence.provider_operation_captured !== "boolean"
        || typeof value.dispatch_evidence.dispatch_result_known !== "boolean"
        || !isNullableBoolean(value.dispatch_evidence.transition_sequence_valid)
        || !isRecord(value.verification_evidence) || Array.isArray(value.verification_evidence)
        || !isNullableString(value.verification_evidence.status)
        || !isOneOf(value.verification_evidence.target_fingerprint_state, ["unchanged", "replaced", "unavailable", "not_applicable"])
        || !isNullableString(value.verification_evidence.observed_state)
        || !isNullableString(value.verification_evidence.observed_health)
        || typeof value.verification_evidence.terminal_evidence !== "boolean"
        || !(value.controlled_reason === null || isOneOf(value.controlled_reason, [
            "not_applicable", "core_unavailable", "missing_core_record", "immutable_request_mismatch",
            "invalid_transition_sequence", "dispatch_outcome_unknown", "dispatch_failed", "verification_pending",
            "verification_failed", "target_replaced", "terminal_state_disagreement",
        ]))
        || !isOneOf(value.safe_next_action, [
            "none", "wait_for_verification", "restore_core_availability", "inspect_target_read_only",
            "preserve_evidence", "operator_review_required", "new_request_only_after_terminal",
        ])) {
        throw new Error("Malformed workflow recovery diagnostic payload.");
    }

    return value as unknown as WorkflowRecoveryDiagnostic;
}

function parseAgentInfo(value: unknown): AgentInfo {
    if (!isRecord(value) || !isRecord(value.install_container)) {
        throw new Error("Malformed Atlas Agent information payload.");
    }

    const capability = value.install_container;
    if (
        typeof value.app_name !== "string"
        || typeof value.version !== "string"
        || typeof value.environment !== "string"
        || typeof value.repository_root !== "string"
        || !isStringArray(value.supported_workflow_phases)
        || !isStringArray(value.supported_verification_statuses)
        || capability.contract_schema !== "agent-install-container-validation-v1"
        || capability.operation !== "install-container"
        || capability.mode !== "validate-only"
        || capability.capability_status !== "unsupported"
        || capability.default_enabled !== false
        || capability.execution_supported !== false
        || capability.dispatch_allowed !== false
        || capability.mutation_allowed !== false
        || capability.replay_allowed !== false
        || typeof capability.runtime !== "string"
        || typeof capability.filesystem !== "string"
        || typeof capability.network !== "string"
        || capability.home_assistant_status !== "blocked"
        || capability.validation_result_available !== false
    ) {
        throw new Error("Malformed Atlas Agent information payload.");
    }

    return value as unknown as AgentInfo;
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

export async function getAgentInfo(): Promise<AgentInfo> {
    const response = await atlasAgent.get<unknown>("/api/v1/agent/info");
    return parseAgentInfo(response.data);
}

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

export async function getWorkflowOperationalLifecycle(
    workflowId: string,
): Promise<WorkflowOperationalLifecycle | null> {
    try {
        const response = await atlasAgent.get<WorkflowOperationalLifecycle>(
            `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/operational-lifecycle`,
        );
        return parseWorkflowOperationalLifecycle(response.data);
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }
        throw error;
    }
}

export async function getWorkflowRecoveryDiagnostic(
    workflowId: string,
): Promise<WorkflowRecoveryDiagnostic | null> {
    try {
        const response = await atlasAgent.get<WorkflowRecoveryDiagnostic>(
            `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/recovery-diagnostic`,
        );
        return parseWorkflowRecoveryDiagnostic(response.data);
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) return null;
        throw error;
    }
}

export async function getWorkflowSupportBundle(
    workflowId: string,
): Promise<OperationalSupportBundle | null> {
    try {
        const response = await atlasAgent.get<OperationalSupportBundle>(
            `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/support-bundle`,
        );
        return response.data;
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) return null;
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

    const workflowList = parseWorkflowListResponse(response.data);
    if (query.effect_kind !== undefined
        && workflowList.items.some((workflow) => workflow.effect_kind !== query.effect_kind)) {
        throw new Error("Malformed workflow list payload.");
    }

    return workflowList;
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
