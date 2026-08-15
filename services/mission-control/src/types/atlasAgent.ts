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
    predecessor_session_id?: string | null;
    successor_session_id?: string | null;
}

export interface CandidatePlanningSuccessorRequest {
    expected_candidate_fingerprint?: string | null;
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

export interface CandidateImplementationTranslationRequest {
    expected_candidate_fingerprint?: string | null;
    expected_plan_fingerprint?: string | null;
    expected_repository_head?: string | null;
}

export interface CandidateImplementationTranslationResponse {
    candidate_planning_session_id: string;
    workflow_session_id: string | null;
    translation_status: string;
    implementation_request_id: string | null;
    exact_approval_request_id: string | null;
    candidate_fingerprint: string | null;
    plan_fingerprint: string | null;
    repository_head: string | null;
    translator_version: string | null;
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

export type WorkflowAuditStageName =
    | "candidate"
    | "planning"
    | "plan"
    | "workflow"
    | "implementation"
    | "approvals"
    | "execution"
    | "verification"
    | "review"
    | "commit";

export type WorkflowAuditStageStatus =
    | "completed"
    | "current"
    | "not_reached"
    | "missing"
    | "invalid"
    | string;

export interface WorkflowAuditSection {
    name: WorkflowAuditStageName;
    status: WorkflowAuditStageStatus;
}

export interface WorkflowAuditFailure {
    valid: boolean;
    failure_code: string | null;
    failure_stage: string | null;
}

export interface WorkflowAuditCandidate {
    status: string;
    candidate_id: string | null;
    candidate_fingerprint: string | null;
    source_recommendation_id: string | null;
    target_id: string | null;
    target_type: string | null;
}

export interface WorkflowAuditPlanning {
    status: string;
    planning_session_id: string | null;
    planning_state: string | null;
    planning_status: string | null;
    created_at: string | null;
    planning_completed_at: string | null;
    candidate_plan_id: string | null;
    candidate_plan_fingerprint: string | null;
}

export interface WorkflowAuditPlan {
    status: string;
    plan_id: string | null;
    candidate_plan_fingerprint: string | null;
    likely_affected_files: string[];
}

export interface WorkflowAuditWorkflow {
    status: string;
    workflow_id: string;
    workflow_source: string;
    workflow_state: string;
}

export interface WorkflowAuditImplementation {
    status: string;
    implementation_request_id: string | null;
    execution_intent: string | null;
    tool: string | null;
    repository_root: string | null;
    repository_head: string | null;
    repository_branch: string | null;
    working_directory: string | null;
    affected_files: string[];
    translator_version: string | null;
}

export interface WorkflowAuditApproval {
    status: string;
    approval_id: string | null;
}

export interface WorkflowAuditApprovals {
    status: string;
    implementation: WorkflowAuditApproval;
    verification: WorkflowAuditApproval;
    commit: WorkflowAuditApproval;
}

export interface WorkflowAuditExecution {
    status: string;
    execution_request_id: string | null;
    execution_status: string | null;
    changed_files_count: number;
    changed_files: string[];
    tool: string | null;
    repository: string | null;
}

export interface WorkflowAuditVerification {
    status: string;
    verification_plan_id: string | null;
    verification_evidence_id: string | null;
    verification_status: string | null;
    changed_files_digest: string | null;
    verification_check_ids: string[];
    repository_head: string | null;
    verification_started_at: string | null;
    verification_completed_at: string | null;
}

export interface WorkflowAuditReview {
    status: string;
    review_result_id: string | null;
    review_report_id: string | null;
    review_status: string | null;
    reviewed_content_fingerprint: string | null;
    changed_files: string[];
}

export interface WorkflowAuditCommit {
    status: string;
    commit_request_id: string | null;
    reviewed_files: string[];
    reviewed_content_fingerprint: string | null;
    expected_branch: string | null;
    expected_head: string | null;
    commit_message: string | null;
    commit_sha: string | null;
    committed_files: string[];
}

export interface WorkflowAuditResponse {
    workflow_id: string;
    workflow_state: string;
    workflow_source: string;
    blocked_reason?: string | null;
    validation: WorkflowAuditFailure;
    timeline: WorkflowAuditSection[];
    candidate: WorkflowAuditCandidate;
    planning: WorkflowAuditPlanning;
    plan: WorkflowAuditPlan;
    workflow: WorkflowAuditWorkflow;
    implementation: WorkflowAuditImplementation;
    approvals: WorkflowAuditApprovals;
    execution: WorkflowAuditExecution;
    verification: WorkflowAuditVerification;
    review: WorkflowAuditReview;
    commit: WorkflowAuditCommit;
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

export interface WorkflowCommitRequestSummary {
    commit_request_id: string;
    repository: string | null;
    branch: string | null;
    expected_head: string | null;
    commit_message: string;
    reviewed_files: string[];
    reviewed_content_fingerprint: string;
    commit_approval_status: string;
}

export interface WorkflowCommitResultSummary {
    commit_sha: string | null;
    commit_message: string | null;
    committed_files: string[];
    completion_time: string | null;
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
    effect_kind: "repository_change" | "operational_action";
    operational_action_request: Record<string, unknown> | null;
    operational_execution: Record<string, unknown> | null;
    approval_presentations: WorkflowApprovalPresentation[];
    timeline: WorkflowTimelineStage[];
    execution: WorkflowExecutionSummary;
    verification_plan: WorkflowVerificationPlanSummary;
    verification_evidence: WorkflowVerificationEvidenceSummary;
    review: WorkflowReviewSummary;
    verification_approval_status: string;
    commit_request: WorkflowCommitRequestSummary | null;
    commit_result: WorkflowCommitResultSummary;
    commit_approval_status: string;
}

export interface WorkflowApprovalPresentation {
    approval_id: string;
    purpose: "implementation" | "candidate_workflow_shell" | "verification" | "commit" | "operational_action";
    decision_status: "pending" | "approved" | "rejected";
    presentation_state: "actionable" | "historical" | "expired" | "superseded" | "resolved";
    actionable: boolean;
    reason: string;
}

export type WorkflowPageResponse = WorkflowDetailResponse;

export type WorkflowState =
    | "awaiting_approval"
    | "awaiting_implementation_approval"
    | "executing"
    | "awaiting_verification_approval"
    | "verifying"
    | "awaiting_commit_approval"
    | "committing"
    | "blocked"
    | "completed"
    | string;

export type WorkflowSource = "candidate" | "manual" | string;

export interface WorkflowSummary {
    workflow_id: string;
    workflow_source: WorkflowSource;
    workflow_state: WorkflowState;
    candidate_id: string | null;
    planning_session_id: string | null;
    repository: string | null;
    target_id: string | null;
    last_result_summary: string;
    timeline: WorkflowTimelineStage[];
}

export interface WorkflowListResponse {
    items: WorkflowSummary[];
    total: number;
    limit: number;
    offset: number;
}

export interface WorkflowListQuery {
    state?: string;
    source?: string;
    candidate_id?: string;
    workflow_id?: string;
    limit?: number;
    offset?: number;
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

export interface WorkflowCommitApprovalResponse {
    workflow_id: string;
    workflow_state: string;
    commit_approval_status: string;
    message: string | null;
}
