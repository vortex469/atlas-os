export interface ApprovalRequest {
    workflow_id?: string | null;
    purpose?: "implementation" | "candidate_workflow_shell" | "verification" | "commit" | "operational_action";
    checkpoint_id: string;
    title: string;
    requested_tool: string;
    requested_command: string[];
    rationale: string;
}

export interface ApprovalDecision {
    request: ApprovalRequest;
    status: "approved" | "rejected";
    reviewer?: string;
    reason?: string;
}

export interface ApprovalResult {
    identifier: string;
    checkpoint_id: string;
    request: ApprovalRequest;
    status: "pending" | "approved" | "rejected";
    created_at?: string;
    reviewer?: string;
    reason?: string;
    presentation_state: "actionable" | "historical" | "expired" | "superseded" | "resolved";
    actionable: boolean;
    presentation_reason: string;
}
