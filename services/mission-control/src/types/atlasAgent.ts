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
