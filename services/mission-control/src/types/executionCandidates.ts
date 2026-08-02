export type ExecutionCandidateStatus = "eligible" | "not_eligible" | "expired" | "rejected" | string;

export type ExecutionCategory = "update" | "restart" | string;

export type ExecutionIntent =
    | "update-compose-stack"
    | "restart-service"
    | "update-container-image"
    | string;

export type ApprovalLevel = "none" | "standard" | "elevated" | "critical" | string;

export type ExecutionConstraint = "service_disruption" | "requires_backup" | string;

export type ExecutionCandidate = {
    id: string;
    source_recommendation_id: string;
    source_subsystem: string;
    recommendation_class: string;
    catalog_item_id?: string | null;
    target_id: string;
    target_type: string;
    execution_category: ExecutionCategory;
    execution_intent: ExecutionIntent;
    status: ExecutionCandidateStatus;
    required_approval_level: ApprovalLevel;
    rationale: string;
    constraints: ExecutionConstraint[];
    evidence_ids: string[];
    compatibility_assessment_id?: string | null;
    compatibility_status?: string | null;
    relationship_ids: string[];
    created_at: string;
    expires_at?: string | null;
};

export type ExecutionCandidatePage = {
    candidates: ExecutionCandidate[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
};

export type ExecutionCandidateListQuery = {
    status?: ExecutionCandidateStatus;
    category?: ExecutionCategory;
    intent?: ExecutionIntent;
    sourceSubsystem?: string;
    targetId?: string;
    limit?: number;
    offset?: number;
};
