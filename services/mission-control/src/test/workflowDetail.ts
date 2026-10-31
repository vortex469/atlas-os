import type { WorkflowDetailResponse } from "../types/atlasAgent";
import { operationalActionRequest } from "./operationalPlanning";

export function workflowDetail(
    overrides: Partial<WorkflowDetailResponse> = {},
): WorkflowDetailResponse {
    const response: WorkflowDetailResponse = {
        workflow_id: "workflow-123",
        workflow_source: "candidate",
        effect_kind: "repository_change",
        workflow_state: "awaiting_implementation_approval",
        planning_session_id: "candidate-plan-123",
        candidate_id: "candidate-123",
        candidate_fingerprint: "candidate-fingerprint-123",
        plan_fingerprint: "plan-fingerprint-123",
        implementation_approval_status: "pending",
        repository: "/opt/atlas",
        working_directory: "/opt/atlas/services/demo",
        translator_version: "candidate-translator-v1",
        affected_files: ["compose.yaml", "services/demo/Dockerfile"],
        implementation_request: {
            immutable_request_id: "impl-request-123",
            tool: "docker-compose",
            working_directory: "/opt/atlas/services/demo",
            affected_files: ["compose.yaml", "services/demo/Dockerfile"],
            repository: "/opt/atlas",
            translator_version: "candidate-translator-v1",
        },
        operational_action_request: null,
        operational_execution: null,
        approval_presentations: [],
        timeline: [
            { name: "Execution Candidate", status: "completed" },
            { name: "Planning Session", status: "completed" },
            { name: "Candidate Plan", status: "completed" },
            { name: "Workflow", status: "completed" },
            { name: "Implementation Approval", status: "current" },
            { name: "Execution", status: "waiting" },
            { name: "Verification", status: "waiting" },
            { name: "Review", status: "waiting" },
            { name: "Commit", status: "waiting" },
        ],
        execution: {
            execution_status: null,
            started_at: null,
            completed_at: null,
            result: null,
            changed_files_count: 0,
            tool: null,
            working_directory: null,
            repository: "/opt/atlas",
            changed_files: [],
            execution_request_id: null,
        },
        verification_plan: {
            verification_plan_id: "verification-plan-123",
            verifier_version: "verifier-v1",
            changed_files_digest: "changed-digest-123",
            verification_check_ids: ["compose-config", "compose-ps"],
            command_backed_checks: ["compose-config", "compose-ps"],
            working_directory: "/opt/atlas/services/demo",
            repository: "/opt/atlas",
            verification_status: "awaiting_verification_approval",
        },
        verification_evidence: {
            verification_status: "passed",
            completed_time: "2026-08-02T17:40:00Z",
            executed_checks: ["compose-config", "compose-ps"],
            check_results: [{ identifier: "compose-config", status: "passed", return_code: 0, duration_seconds: 1.2, output_truncated: false }],
            repository_head: "abc123",
            changed_files_digest: "changed-digest-123",
        },
        review: {
            review_result: "approved",
            review_status: "approved",
            approved: true,
            evidence_summary: "0 findings, 0 recommendations",
            changed_files: ["compose.yaml"],
            review_fingerprint: "review-fingerprint-123",
            model_assisted_review: "Disabled",
        },
        verification_approval_status: "pending",
        commit_request: null,
        commit_result: {
            commit_sha: null,
            commit_message: null,
            committed_files: [],
            completion_time: null,
        },
        commit_approval_status: "not_requested",
        ...overrides,
    };

    if (response.effect_kind === "operational_action") {
        if (!Object.hasOwn(overrides, "operational_action_request")) {
            response.operational_action_request = operationalActionRequest();
        }
        if (!Object.hasOwn(overrides, "approval_presentations")) {
            const pending = response.implementation_approval_status === "pending";
            const actionable = pending && response.workflow_state === "awaiting_implementation_approval";
            response.approval_presentations = [{
                approval_id: "approval-action-123",
                purpose: "operational_action",
                decision_status: pending ? "pending" : response.implementation_approval_status === "approved" ? "approved" : "rejected",
                presentation_state: pending ? actionable ? "actionable" : "historical" : "resolved",
                actionable,
                reason: "Synthetic server approval presentation.",
            }];
        }
    }

    return response;
}
