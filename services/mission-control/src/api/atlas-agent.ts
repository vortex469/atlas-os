import axios, { isAxiosError } from "axios";

import type {
    AgentInfo,
    CandidatePlanApiResponse,
    CandidatePlanningRequest,
    CandidatePlanningSuccessorRequest,
    CandidatePlanningResponse,
    OperationalCandidatePlanApiResponse,
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

function isNonEmptyString(value: unknown): value is string {
    return typeof value === "string" && value.trim().length > 0;
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

function isPlainRecord(value: unknown): value is Record<string, unknown> {
    return isRecord(value) && !Array.isArray(value);
}

function hasNullableStringFields(value: Record<string, unknown>, fields: readonly string[]): boolean {
    return fields.every((field) => isNullableString(value[field]));
}

function hasStringArrayFields(value: Record<string, unknown>, fields: readonly string[]): boolean {
    return fields.every((field) => isStringArray(value[field]));
}

function isWorkflowAuditApproval(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && isNullableString(value.approval_id);
}

function isWorkflowAuditSection(value: unknown): boolean {
    return isPlainRecord(value)
        && isOneOf(value.name, [
            "candidate", "planning", "plan", "workflow", "implementation", "approvals",
            "execution", "verification", "review", "commit",
        ])
        && isOneOf(value.status, ["completed", "current", "not_reached", "missing", "invalid", "inconsistent"]);
}

function isWorkflowAuditValidation(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.valid === "boolean"
        && isNullableString(value.failure_code)
        && isNullableString(value.failure_stage);
}

function isWorkflowAuditCandidate(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, [
            "candidate_id", "candidate_fingerprint", "source_recommendation_id", "target_id", "target_type",
        ]);
}

function isWorkflowAuditPlanning(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, [
            "planning_session_id", "planning_state", "planning_status", "candidate_plan_id",
            "candidate_plan_fingerprint",
        ])
        && isNullableDateTime(value.created_at)
        && isNullableDateTime(value.planning_completed_at);
}

function isWorkflowAuditPlan(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, ["plan_id", "candidate_plan_fingerprint"])
        && hasStringArrayFields(value, ["likely_affected_files"]);
}

function isWorkflowAuditWorkflow(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && isSafeRouteId(value.workflow_id)
        && typeof value.workflow_source === "string"
        && typeof value.workflow_state === "string";
}

function isWorkflowAuditImplementation(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, [
            "implementation_request_id", "execution_intent", "tool", "repository_root", "repository_head",
            "repository_branch", "working_directory", "translator_version",
        ])
        && hasStringArrayFields(value, ["affected_files"]);
}

function isWorkflowAuditApprovals(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && isWorkflowAuditApproval(value.shell)
        && isWorkflowAuditApproval(value.implementation)
        && isWorkflowAuditApproval(value.verification)
        && isWorkflowAuditApproval(value.commit);
}

function isWorkflowAuditExecution(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, ["execution_request_id", "execution_status", "tool", "repository"])
        && isNonNegativeSafeInteger(value.changed_files_count)
        && hasStringArrayFields(value, ["changed_files"]);
}

function isWorkflowAuditVerification(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, [
            "verification_plan_id", "verification_evidence_id", "verification_status", "changed_files_digest",
            "repository_head",
        ])
        && hasStringArrayFields(value, ["verification_check_ids"])
        && isNullableDateTime(value.verification_started_at)
        && isNullableDateTime(value.verification_completed_at);
}

function isWorkflowAuditReview(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, [
            "review_result_id", "review_report_id", "review_status", "reviewed_content_fingerprint",
        ])
        && hasStringArrayFields(value, ["changed_files"]);
}

function isWorkflowAuditCommit(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.status === "string"
        && hasNullableStringFields(value, [
            "commit_request_id", "reviewed_content_fingerprint", "expected_branch", "expected_head",
            "commit_message", "commit_sha",
        ])
        && hasStringArrayFields(value, ["reviewed_files", "committed_files"]);
}

function parseWorkflowAuditResponse(value: unknown): WorkflowAuditResponse {
    if (!isPlainRecord(value)
        || !isSafeRouteId(value.workflow_id)
        || !isOneOf(value.effect_kind, ["repository_change", "operational_action"])
        || typeof value.workflow_state !== "string"
        || typeof value.workflow_source !== "string"
        || !(value.blocked_reason === undefined || isNullableString(value.blocked_reason))
        || !isWorkflowAuditValidation(value.validation)
        || !Array.isArray(value.timeline) || !value.timeline.every(isWorkflowAuditSection)
        || !isWorkflowAuditCandidate(value.candidate)
        || !isWorkflowAuditPlanning(value.planning)
        || !isWorkflowAuditPlan(value.plan)
        || !isWorkflowAuditWorkflow(value.workflow)
        || !isWorkflowAuditImplementation(value.implementation)
        || !isWorkflowAuditApprovals(value.approvals)
        || !isWorkflowAuditExecution(value.execution)
        || !isWorkflowAuditVerification(value.verification)
        || !isWorkflowAuditReview(value.review)
        || !isWorkflowAuditCommit(value.commit)) {
        throw new Error("Malformed workflow audit payload.");
    }

    return value as unknown as WorkflowAuditResponse;
}

function isWorkflowImplementationRequest(value: unknown): boolean {
    return isPlainRecord(value)
        && typeof value.immutable_request_id === "string"
        && typeof value.tool === "string"
        && typeof value.working_directory === "string"
        && hasStringArrayFields(value, ["affected_files"])
        && typeof value.repository === "string"
        && isNullableString(value.translator_version);
}

function isWorkflowOperationalActionRequest(value: unknown): boolean {
    if (value === null) return true;
    return isPlainRecord(value)
        && typeof value.request_id === "string"
        && typeof value.request_digest === "string"
        && typeof value.provider_id === "string"
        && typeof value.resource_id === "string"
        && typeof value.resource_type === "string"
        && typeof value.target_fingerprint === "string"
        && isNullableString(value.target_version)
        && typeof value.expected_pre_state === "string"
        && typeof value.intended_action === "string"
        && typeof value.disruption_scope === "string"
        && isPlainRecord(value.verification)
        && typeof value.verification.pre_state === "string"
        && typeof value.verification.expected_post_state === "string"
        && typeof value.verification.health_requirement === "string"
        && typeof value.verification.unknown_outcome_policy === "string"
        && typeof value.generated_at === "string" && Number.isFinite(Date.parse(value.generated_at))
        && typeof value.expires_at === "string" && Number.isFinite(Date.parse(value.expires_at))
        && value.execution_enabled === false;
}

function isWorkflowApprovalPresentation(value: unknown): boolean {
    return isPlainRecord(value)
        && isSafeRouteId(value.approval_id)
        && isOneOf(value.purpose, ["implementation", "candidate_workflow_shell", "verification", "commit", "operational_action"])
        && isOneOf(value.decision_status, ["pending", "approved", "rejected"])
        && isOneOf(value.presentation_state, ["actionable", "historical", "expired", "superseded", "resolved"])
        && typeof value.actionable === "boolean"
        && typeof value.reason === "string";
}

function isWorkerReconciliation(value: unknown): boolean {
    if (value === null) return true;
    return isPlainRecord(value)
        && isSafeRouteId(value.request_id)
        && (value.request_digest === undefined || isNonEmptyString(value.request_digest))
        && isOneOf(value.outcome, ["unknown", "known"])
        && typeof value.can_check_result === "boolean"
        && typeof value.message === "string";
}

function isWorkflowExecutionSummary(value: unknown): boolean {
    if (!isPlainRecord(value)
        || !isNullableString(value.execution_status)
        || !isNullableDateTime(value.started_at)
        || !isNullableDateTime(value.completed_at)
        || !isNullableString(value.result)
        || !isNonNegativeSafeInteger(value.changed_files_count)
        || !isNullableString(value.tool)
        || !isNullableString(value.working_directory)
        || !isNullableString(value.repository)
        || !hasStringArrayFields(value, ["changed_files"])
        || !isNullableString(value.execution_request_id)) {
        return false;
    }

    if (value.output_capture === undefined) return true;
    return Array.isArray(value.output_capture) && value.output_capture.every((capture) =>
        isPlainRecord(capture)
        && typeof capture.stream === "string"
        && isNonNegativeSafeInteger(capture.retained_bytes)
        && (capture.observed_bytes === null || isNonNegativeSafeInteger(capture.observed_bytes))
        && typeof capture.truncated === "boolean");
}

function isWorkflowVerificationPlan(value: unknown): boolean {
    return isPlainRecord(value)
        && isNullableString(value.verification_plan_id)
        && isNullableString(value.verifier_version)
        && isNullableString(value.changed_files_digest)
        && hasStringArrayFields(value, ["verification_check_ids", "command_backed_checks"])
        && isNullableString(value.working_directory)
        && isNullableString(value.repository)
        && typeof value.verification_status === "string";
}

function isWorkflowVerificationEvidence(value: unknown): boolean {
    return isPlainRecord(value)
        && isNullableString(value.verification_status)
        && isNullableDateTime(value.completed_time)
        && hasStringArrayFields(value, ["executed_checks"])
        && Array.isArray(value.check_results)
        && value.check_results.every((result) => isPlainRecord(result)
            && Object.values(result).every((item) => item === null || typeof item === "string"
                || typeof item === "boolean" || (typeof item === "number" && Number.isFinite(item))))
        && isNullableString(value.repository_head)
        && isNullableString(value.changed_files_digest);
}

function isWorkflowReviewSummary(value: unknown): boolean {
    return isPlainRecord(value)
        && isNullableString(value.review_result)
        && isNullableString(value.review_status)
        && isNullableBoolean(value.approved)
        && isNullableString(value.evidence_summary)
        && hasStringArrayFields(value, ["changed_files"])
        && isNullableString(value.review_fingerprint)
        && typeof value.model_assisted_review === "string";
}

function isWorkflowCommitRequest(value: unknown): boolean {
    if (value === null) return true;
    return isPlainRecord(value)
        && isSafeRouteId(value.commit_request_id)
        && isNullableString(value.repository)
        && isNullableString(value.branch)
        && isNullableString(value.expected_head)
        && typeof value.commit_message === "string"
        && hasStringArrayFields(value, ["reviewed_files"])
        && typeof value.reviewed_content_fingerprint === "string"
        && typeof value.commit_approval_status === "string";
}

function isWorkflowCommitResult(value: unknown): boolean {
    return isPlainRecord(value)
        && isNullableString(value.commit_sha)
        && isNullableString(value.commit_message)
        && hasStringArrayFields(value, ["committed_files"])
        && isNullableDateTime(value.completion_time);
}

function parseWorkflowDetailResponse(value: unknown): WorkflowDetailResponse {
    if (!isPlainRecord(value)
        || !isSafeRouteId(value.workflow_id)
        || typeof value.workflow_source !== "string"
        || typeof value.workflow_state !== "string"
        || !isNullableString(value.planning_session_id)
        || !isNullableString(value.candidate_id)
        || !isNullableString(value.candidate_fingerprint)
        || !isNullableString(value.plan_fingerprint)
        || typeof value.implementation_approval_status !== "string"
        || !isNullableString(value.repository)
        || !isNullableString(value.working_directory)
        || !isNullableString(value.translator_version)
        || !hasStringArrayFields(value, ["affected_files"])
        || !(value.implementation_request === null || isWorkflowImplementationRequest(value.implementation_request))
        || !isOneOf(value.effect_kind, ["repository_change", "operational_action"])
        || !isWorkflowOperationalActionRequest(value.operational_action_request)
        || !(value.operational_execution === null || isPlainRecord(value.operational_execution))
        || !Array.isArray(value.approval_presentations)
        || !value.approval_presentations.every(isWorkflowApprovalPresentation)
        || new Set(value.approval_presentations.map((item) => (item as Record<string, unknown>).approval_id)).size !== value.approval_presentations.length
        || !Array.isArray(value.timeline)
        || !value.timeline.every((stage) => isPlainRecord(stage)
            && typeof stage.name === "string" && typeof stage.status === "string")
        || !isWorkflowExecutionSummary(value.execution)
        || !isWorkerReconciliation(value.worker_reconciliation === undefined ? null : value.worker_reconciliation)
        || !isWorkflowVerificationPlan(value.verification_plan)
        || !isWorkflowVerificationEvidence(value.verification_evidence)
        || !isWorkflowReviewSummary(value.review)
        || typeof value.verification_approval_status !== "string"
        || !isWorkflowCommitRequest(value.commit_request)
        || !isWorkflowCommitResult(value.commit_result)
        || typeof value.commit_approval_status !== "string") {
        throw new Error("Malformed workflow detail payload.");
    }

    return value as unknown as WorkflowDetailResponse;
}

function isCandidatePlan(value: unknown): value is CandidatePlanApiResponse {
    return isPlainRecord(value)
        && isSafeRouteId(value.identifier)
        && isSafeRouteId(value.session_id)
        && isSafeRouteId(value.candidate_id)
        && isNonEmptyString(value.candidate_fingerprint)
        && typeof value.title === "string"
        && typeof value.objective === "string"
        && hasStringArrayFields(value, [
            "assumptions", "constraints", "proposed_steps", "likely_affected_components",
            "likely_affected_files", "verification_strategy", "rollback_considerations",
            "unresolved_questions", "evidence_ids",
        ])
        && typeof value.created_at === "string" && Number.isFinite(Date.parse(value.created_at))
        && isNullableString(value.repository_branch)
        && isNullableString(value.repository_head)
        && isNonEmptyString(value.revalidated_candidate_fingerprint);
}

function isOperationalCandidatePlan(value: unknown): value is OperationalCandidatePlanApiResponse {
    return isPlainRecord(value)
        && isSafeRouteId(value.identifier)
        && isSafeRouteId(value.session_id)
        && isSafeRouteId(value.candidate_id)
        && isNonEmptyString(value.candidate_fingerprint)
        && value.effect_kind === "operational_action"
        && isNonEmptyString(value.execution_intent)
        && isNonEmptyString(value.provider_id)
        && isNonEmptyString(value.resource_id)
        && isNonEmptyString(value.resource_type)
        && isNonEmptyString(value.target_fingerprint)
        && isNullableString(value.target_version)
        && isNonEmptyString(value.expected_pre_state)
        && isNonEmptyString(value.intended_action)
        && isNonEmptyString(value.disruption_scope)
        && isPlainRecord(value.verification)
        && isNonEmptyString(value.verification.pre_state)
        && isNonEmptyString(value.verification.expected_post_state)
        && isNonEmptyString(value.verification.identity_fingerprint)
        && isNonEmptyString(value.verification.health_requirement)
        && isNonEmptyString(value.verification.unknown_outcome_policy)
        && hasStringArrayFields(value, ["failure_considerations", "evidence_ids"])
        && typeof value.created_at === "string" && Number.isFinite(Date.parse(value.created_at))
        && isNonEmptyString(value.revalidated_candidate_fingerprint);
}

function isCandidatePlanningFailure(value: unknown): boolean {
    return value === null || (isPlainRecord(value)
        && typeof value.code === "string"
        && typeof value.message === "string");
}

function parseCandidatePlanningResponse(value: unknown): CandidatePlanningResponse {
    if (!isPlainRecord(value)
        || !(value.session_id === null || isSafeRouteId(value.session_id))
        || !isSafeRouteId(value.candidate_id)
        || typeof value.status !== "string"
        || typeof value.planning_allowed !== "boolean"
        || typeof value.intake_status !== "string"
        || !hasStringArrayFields(value, ["intake_reason_codes"])
        || !isNullableString(value.candidate_fingerprint)
        || !isNullableString(value.unsupported_reason)
        || !(value.plan === null || isCandidatePlan(value.plan))
        || !(value.operational_plan === undefined || value.operational_plan === null || isOperationalCandidatePlan(value.operational_plan))
        || !isCandidatePlanningFailure(value.planning_failure)
        || !(value.predecessor_session_id === undefined || value.predecessor_session_id === null || isSafeRouteId(value.predecessor_session_id))
        || !(value.successor_session_id === undefined || value.successor_session_id === null || isSafeRouteId(value.successor_session_id))) {
        throw new Error("Malformed candidate planning response.");
    }

    return value as unknown as CandidatePlanningResponse;
}

function parseCandidateWorkflowResponse(value: unknown): CandidateWorkflowResponse {
    if (!isPlainRecord(value)
        || !isSafeRouteId(value.candidate_planning_session_id)
        || !isSafeRouteId(value.candidate_id)
        || !isNullableString(value.candidate_fingerprint)
        || !isNullableString(value.candidate_plan_id)
        || !isNullableString(value.candidate_plan_fingerprint)
        || !isNullableString(value.workflow_session_id)
        || !isNullableString(value.workflow_status)
        || !isNullableString(value.implementation_approval_request_id)
        || !isNonEmptyString(value.conversion_status)
        || !isNullableString(value.core_revalidation_status)
        || !hasStringArrayFields(value, ["reason_codes"])
        || !isCandidatePlanningFailure(value.failure)) {
        throw new Error("Malformed candidate workflow response.");
    }

    return value as unknown as CandidateWorkflowResponse;
}

function parseCandidateImplementationTranslationResponse(value: unknown): CandidateImplementationTranslationResponse {
    if (!isPlainRecord(value)
        || !isSafeRouteId(value.candidate_planning_session_id)
        || !(value.workflow_session_id === null || isSafeRouteId(value.workflow_session_id))
        || !isOneOf(value.translation_status, [
            "implementation_ready", "implementation_not_supported",
            "implementation_translation_failed", "stale_before_implementation",
        ])
        || !(value.implementation_request_id === null || isSafeRouteId(value.implementation_request_id))
        || !(value.exact_approval_request_id === null || isSafeRouteId(value.exact_approval_request_id))
        || !isNullableString(value.candidate_fingerprint)
        || !isNullableString(value.plan_fingerprint)
        || !isNullableString(value.repository_head)
        || !isNullableString(value.translator_version)
        || !hasStringArrayFields(value, ["reason_codes"])
        || !isCandidatePlanningFailure(value.failure)) {
        throw new Error("Malformed candidate implementation response.");
    }

    if (value.translation_status === "implementation_ready"
        && (value.failure !== null
            || !isSafeRouteId(value.workflow_session_id)
            || !isSafeRouteId(value.implementation_request_id)
            || !isSafeRouteId(value.exact_approval_request_id))) {
        throw new Error("Malformed candidate implementation response.");
    }

    return value as unknown as CandidateImplementationTranslationResponse;
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

    return parseCandidatePlanningResponse(response.data);
}

export async function getCandidatePlanningSession(
    sessionId: string,
): Promise<CandidatePlanningResponse | null> {
    try {
        const response = await atlasAgent.get<unknown>(
            `/candidate-planning/${encodeURIComponent(sessionId)}`,
        );

        return parseCandidatePlanningResponse(response.data);
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
    const response = await atlasAgent.post<unknown>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/plan`,
    );

    return parseCandidatePlanningResponse(response.data);
}

export async function getCandidatePlan(
    sessionId: string,
): Promise<CandidatePlanApiResponse | null> {
    try {
        const response = await atlasAgent.get<unknown>(
            `/candidate-planning/${encodeURIComponent(sessionId)}/plan`,
        );

        const plan = response.data;
        if (!isCandidatePlan(plan)) throw new Error("Malformed candidate plan response.");
        return plan;
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
    const response = await atlasAgent.post<unknown>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/successor`,
        request,
    );

    return parseCandidatePlanningResponse(response.data);
}

export async function createCandidateWorkflowShell(
    sessionId: string,
    request?: CandidateWorkflowRequest,
): Promise<CandidateWorkflowResponse> {
    const response = await atlasAgent.post<unknown>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/workflow`,
        request,
    );

    return parseCandidateWorkflowResponse(response.data);
}

export async function createCandidateImplementationRequest(
    sessionId: string,
    request?: CandidateImplementationTranslationRequest,
): Promise<CandidateImplementationTranslationResponse> {
    const response = await atlasAgent.post<unknown>(
        `/candidate-planning/${encodeURIComponent(sessionId)}/implementation`,
        request,
    );

    return parseCandidateImplementationTranslationResponse(response.data);
}

export async function getWorkflowDetail(
    workflowId: string,
): Promise<WorkflowDetailResponse | null> {
    try {
        const response = await atlasAgent.get<WorkflowDetailResponse>(
            `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/implementation-request`,
        );

        return parseWorkflowDetailResponse(response.data);
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

        return parseWorkflowAuditResponse(response.data);
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
    const response = await atlasAgent.post<unknown>(
        `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/implementation-approval`,
        { workflow_id: workflowId, decision },
    );

    return parseWorkflowApprovalResponse<WorkflowImplementationApprovalResponse>(
        response.data, workflowId, decision, "implementation_approval_status",
    );
}

export async function submitWorkflowVerificationApproval(
    workflowId: string,
    decision: WorkflowImplementationDecision,
): Promise<WorkflowVerificationApprovalResponse> {
    const response = await atlasAgent.post<unknown>(
        `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/verification-approval`,
        { workflow_id: workflowId, decision },
    );

    return parseWorkflowApprovalResponse<WorkflowVerificationApprovalResponse>(
        response.data, workflowId, decision, "verification_approval_status",
    );
}

export async function submitWorkflowCommitApproval(
    workflowId: string,
    decision: WorkflowImplementationDecision,
): Promise<WorkflowCommitApprovalResponse> {
    const response = await atlasAgent.post<unknown>(
        `/api/v1/agent/workflows/${encodeURIComponent(workflowId)}/commit-approval`,
        { workflow_id: workflowId, decision },
    );

    return parseWorkflowApprovalResponse<WorkflowCommitApprovalResponse>(
        response.data, workflowId, decision, "commit_approval_status",
    );
}

function parseWorkflowApprovalResponse<T extends {
    workflow_id: string;
    workflow_state: string;
    message: string | null;
}>(
    value: unknown,
    workflowId: string,
    decision: WorkflowImplementationDecision,
    statusField: "implementation_approval_status" | "verification_approval_status" | "commit_approval_status",
): T {
    const expectedStatus = decision === "approve" ? "approved" : "rejected";
    if (!isRecord(value)
        || value.workflow_id !== workflowId
        || !isNonEmptyString(value.workflow_state)
        || value[statusField] !== expectedStatus
        || !isNullableString(value.message)) {
        throw new Error("Malformed workflow approval response.");
    }

    return value as T;
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
        const responseData = error.response?.data;
        const detail = isRecord(responseData) ? responseData.detail : undefined;
        if (typeof detail === "string" && detail.trim()) return detail;
        if (isRecord(detail) && typeof detail.message === "string" && detail.message.trim()) {
            return detail.message;
        }
        return error.message?.trim() || fallback;
    }

    return error instanceof Error && error.message.trim() ? error.message : fallback;
}
