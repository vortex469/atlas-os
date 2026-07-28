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
