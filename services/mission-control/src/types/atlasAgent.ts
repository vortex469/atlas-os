export interface RepositoryStatus {
    root: string;
    branch: string | null;
    head_commit: string | null;
    is_clean: boolean;
    modified_files: string[];
    staged_files: string[];
    untracked_files: string[];
}

export interface SprintStatus {
    checkpoint_id: string;
    title: string;
    goal: string;
    phase: string;
}

export interface VerificationCheck {
    identifier: string;
    argv: string[];
    working_directory: string;
    status: string;
    return_code: number | null;
    stdout: string;
    stderr: string;
    duration_seconds: number;
    error: string | null;
}

export interface VerificationReport {
    repository_root: string;
    status: string;
    duration_seconds: number;
    results: VerificationCheck[];
}

export interface ReviewFinding {
    code: string;
    category: string;
    severity: string;
    summary: string;
    evidence: string;
    recommendation: string;
}

export interface ReviewReport {
    request_id: string;
    checkpoint_id: string;
    status: string;
    findings: ReviewFinding[];
    recommendations: string[];
}

export interface CandidatePlanningRequest {
    candidate_id: string;
    expected_candidate_fingerprint?: string | null;
}

export interface CandidatePlanningFailure {
    code: string;
    message: string;
}

export interface CandidatePlanApiResponse {
    identifier: string;
    session_id: string;
    candidate_id: string;
    candidate_fingerprint: string;
    title: string;
    objective: string;
    assumptions: string[];
    constraints: string[];
    proposed_steps: string[];
    likely_affected_components: string[];
    likely_affected_files: string[];
    verification_strategy: string[];
    rollback_considerations: string[];
    unresolved_questions: string[];
    evidence_ids: string[];
    created_at: string;
    repository_branch: string | null;
    repository_head: string | null;
    revalidated_candidate_fingerprint: string;
}

export interface CandidatePlanningResponse {
    session_id: string | null;
    candidate_id: string;
    status: string;
    planning_allowed: boolean;
    intake_status: string;
    intake_reason_codes: string[];
    candidate_fingerprint: string | null;
    unsupported_reason: string | null;
    plan: CandidatePlanApiResponse | null;
    planning_failure: CandidatePlanningFailure | null;
}

export interface CandidateWorkflowRequest {
    expected_candidate_fingerprint?: string | null;
    expected_plan_fingerprint?: string | null;
}

export interface CandidateWorkflowResponse {
    candidate_planning_session_id: string;
    candidate_id: string;
    candidate_fingerprint: string | null;
    candidate_plan_id: string | null;
    candidate_plan_fingerprint: string | null;
    workflow_session_id: string | null;
    workflow_status: string | null;
    implementation_approval_request_id: string | null;
    conversion_status: string;
    core_revalidation_status: string | null;
    reason_codes: string[];
    failure: CandidatePlanningFailure | null;
}

export interface WorkflowImplementationRequestSummary {
    immutable_request_id: string;
    tool: string;
    working_directory: string;
    affected_files: string[];
    repository: string;
    translator_version: string | null;
}

export interface WorkflowTimelineStage {
    name: string;
    status: "completed" | "current" | "waiting" | "blocked" | "failed" | string;
}

export interface WorkflowExecutionSummary {
    execution_status: string | null;
    started_at: string | null;
    completed_at: string | null;
    result: string | null;
    changed_files_count: number;
    tool: string | null;
    working_directory: string | null;
    repository: string | null;
    changed_files: string[];
    execution_request_id: string | null;
}

export interface WorkflowVerificationPlanSummary {
    verification_plan_id: string | null;
    verifier_version: string | null;
    changed_files_digest: string | null;
    verification_check_ids: string[];
    command_backed_checks: string[];
    working_directory: string | null;
    repository: string | null;
    verification_status: string;
}

export interface WorkflowVerificationEvidenceSummary {
    verification_status: string | null;
    completed_time: string | null;
    executed_checks: string[];
    check_results: Array<Record<string, string | number | boolean | null>>;
    repository_head: string | null;
    changed_files_digest: string | null;
}

export interface WorkflowReviewSummary {
    review_result: string | null;
    review_status: string | null;
    approved: boolean | null;
    evidence_summary: string | null;
    changed_files: string[];
    review_fingerprint: string | null;
    model_assisted_review: string;
}

export interface WorkflowDetailResponse {
    workflow_id: string;
    workflow_source: string;
    workflow_state: string;
    planning_session_id: string | null;
    candidate_id: string | null;
    candidate_fingerprint: string | null;
    plan_fingerprint: string | null;
    implementation_approval_status: string;
    repository: string | null;
    working_directory: string | null;
    translator_version: string | null;
    affected_files: string[];
    implementation_request: WorkflowImplementationRequestSummary | null;
    timeline: WorkflowTimelineStage[];
    execution: WorkflowExecutionSummary;
    verification_plan: WorkflowVerificationPlanSummary;
    verification_evidence: WorkflowVerificationEvidenceSummary;
    review: WorkflowReviewSummary;
    verification_approval_status: string;
}

export type WorkflowImplementationDecision = "approve" | "reject";

export interface WorkflowImplementationApprovalResponse {
    workflow_id: string;
    workflow_state: string;
    implementation_approval_status: string;
    message: string | null;
}

export interface WorkflowVerificationApprovalResponse {
    workflow_id: string;
    workflow_state: string;
    verification_approval_status: string;
    message: string | null;
}
