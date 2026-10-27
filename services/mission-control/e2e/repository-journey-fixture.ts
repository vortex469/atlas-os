import { isDeepStrictEqual } from "node:util";
import type { Page } from "@playwright/test";
import type { ExecutionCandidate } from "../src/types/executionCandidates";
import { operationalPlan, operationalActionRequest } from "../src/test/operationalPlanning";
import { operationalLifecycle, operationalDiagnostic } from "../src/test/operationalLifecycle";
import type {
    CandidatePlanApiResponse, CandidatePlanningResponse, CandidateWorkflowResponse,
    WorkflowAuditResponse, WorkflowDetailResponse,
} from "../src/types/atlasAgent";

// Synthetic public DTOs only. Every API request is intercepted, and writes
// must match the next exact request in this simulated operator journey.
export const journey = {
    candidate: `candidate-browser-journey-${"a".repeat(64)}`, session: `planning-browser-journey-${"b".repeat(64)}`,
    workflow: `workflow-browser-journey-${"c".repeat(64)}`, plan: `plan-browser-journey-${"d".repeat(64)}`,
    candidateFingerprint: "candidate-fingerprint-browser-journey",
    planFingerprint: "plan-fingerprint-browser-journey",
    head: "1".repeat(40), commit: "2".repeat(40),
    repository: "/workspace/browser-fixture", file: "compose.production.yaml",
};
const observedAt = "2026-01-01T12:00:00Z";
type Phase = "implementation" | "verification" | "commit" | "completed" | "rejected";
type JourneyWrite = { path: string; body: unknown };

const candidate: ExecutionCandidate = {
    effect_kind: "repository_change",
    id: journey.candidate, source_recommendation_id: "recommendation-browser-journey",
    source_subsystem: "ace", recommendation_class: "maintenance", target_id: "fixture-service",
    target_type: "service", execution_category: "update", execution_intent: "update-compose-stack",
    status: "eligible", required_approval_level: "standard", rationale: "Review a simulated repository change.",
    constraints: [], evidence_ids: [], compatibility_assessment_id: null,
    compatibility_status: "compatible", relationship_ids: [], created_at: observedAt,
    expires_at: "2999-01-01T12:00:00Z",
};
export const maintenanceCandidate: ExecutionCandidate = {
    ...candidate, source_subsystem: "operator-intent", execution_category: "restart", execution_intent: "restart-service",
    effect_kind: "operational_action",
    target_id: "110", target_type: "qemu", rationale: "Review a simulated service restart.",
    expires_at: "2026-10-26T00:15:00.000Z",
};
const plan: CandidatePlanApiResponse = {
    identifier: journey.plan, session_id: journey.session, candidate_id: journey.candidate,
    candidate_fingerprint: journey.candidateFingerprint, title: "Update fixture compose configuration",
    objective: "Review one simulated repository edit.", assumptions: [],
    constraints: ["Separate exact approval for implementation, verification and commit."],
    proposed_steps: ["Edit the compose file.", "Verify configuration.", "Review and commit locally."],
    likely_affected_components: ["fixture-service"], likely_affected_files: [journey.file],
    verification_strategy: ["Check the compose configuration."], rollback_considerations: ["Restore the prior file."],
    unresolved_questions: [], evidence_ids: [], created_at: observedAt,
    repository_branch: "fixture-branch", repository_head: journey.head,
    revalidated_candidate_fingerprint: journey.candidateFingerprint,
};
function planningSession(ready: boolean): CandidatePlanningResponse {
    return {
        session_id: journey.session, candidate_id: journey.candidate,
        status: ready ? "plan_ready" : "ready_for_planning", planning_allowed: true,
        intake_status: "accepted_for_planning", intake_reason_codes: [],
        candidate_fingerprint: journey.candidateFingerprint, unsupported_reason: null,
        plan: ready ? plan : null, planning_failure: null,
    };
}
const shell: CandidateWorkflowResponse = {
    candidate_planning_session_id: journey.session, candidate_id: journey.candidate,
    candidate_fingerprint: journey.candidateFingerprint, candidate_plan_id: journey.plan,
    candidate_plan_fingerprint: journey.planFingerprint, workflow_session_id: journey.workflow,
    workflow_status: "awaiting_approval", implementation_approval_request_id: "approval-browser-implementation",
    conversion_status: "workflow_created", core_revalidation_status: "accepted_for_planning",
    reason_codes: [], failure: null,
};

export function workflowDetail(phase: Phase, approved: boolean): WorkflowDetailResponse {
    const implemented = ["verification", "commit", "completed"].includes(phase);
    const verified = ["commit", "completed"].includes(phase);
    const completed = phase === "completed";
    const workflowState = phase === "rejected" ? "blocked" : completed ? "completed" : `awaiting_${phase}_approval`;
    const approval = phase === "rejected" ? "rejected" : approved ? "approved" : "pending";
    const labels = ["Execution Candidate", "Planning Session", "Candidate Plan", "Workflow", "Implementation Approval", "Execution", "Verification", "Review", "Commit"];
    const currentIndex = phase === "implementation" || phase === "rejected" ? 4 : phase === "verification" ? 6 : 8;
    return {
        workflow_id: journey.workflow, workflow_source: "candidate", effect_kind: "repository_change",
        workflow_state: workflowState, planning_session_id: journey.session, candidate_id: journey.candidate,
        candidate_fingerprint: journey.candidateFingerprint, plan_fingerprint: journey.planFingerprint,
        implementation_approval_status: implemented ? "approved" : approval,
        verification_approval_status: verified ? "approved" : phase === "verification" ? approval : "not_requested",
        commit_approval_status: completed ? "approved" : phase === "commit" ? approval : "not_requested",
        repository: journey.repository, working_directory: journey.repository,
        translator_version: "fixture-translator-v1", affected_files: [journey.file],
        implementation_request: { immutable_request_id: "implementation-browser-journey", tool: "fixture-editor",
            repository: journey.repository, working_directory: journey.repository,
            affected_files: [journey.file], translator_version: "fixture-translator-v1" },
        operational_action_request: null, operational_execution: null, approval_presentations: [],
        timeline: labels.map((name, index) => ({ name, status: completed || index < currentIndex ? "completed" : index === currentIndex ? "current" : "waiting" })),
        execution: { execution_status: implemented ? "succeeded" : null, started_at: implemented ? observedAt : null,
            completed_at: implemented ? observedAt : null, result: implemented ? "Simulated file edit completed." : null,
            changed_files_count: implemented ? 1 : 0, tool: implemented ? "fixture-editor" : null,
            working_directory: journey.repository, repository: journey.repository,
            changed_files: implemented ? [journey.file] : [], execution_request_id: implemented ? "execution-browser-journey" : null },
        verification_plan: { verification_plan_id: implemented ? "verification-browser-journey" : null,
            verifier_version: implemented ? "fixture-verifier-v1" : null,
            changed_files_digest: implemented ? "browser-changed-files-digest" : null,
            verification_check_ids: implemented ? ["compose-config"] : [], command_backed_checks: implemented ? ["compose-config"] : [],
            working_directory: journey.repository, repository: journey.repository,
            verification_status: verified ? "passed" : implemented ? "awaiting_verification_approval" : "not_reached" },
        verification_evidence: { verification_status: verified ? "passed" : null, completed_time: verified ? observedAt : null,
            executed_checks: verified ? ["compose-config"] : [], check_results: verified ? [{ identifier: "compose-config", status: "passed", return_code: 0 }] : [],
            repository_head: verified ? journey.head : null, changed_files_digest: verified ? "browser-changed-files-digest" : null },
        review: { review_result: verified ? "approved" : null, review_status: verified ? "approved" : null,
            approved: verified ? true : null, evidence_summary: verified ? "Simulated review passed." : null,
            changed_files: verified ? [journey.file] : [], review_fingerprint: verified ? "review-browser-fingerprint" : null,
            model_assisted_review: "Disabled" },
        commit_request: verified ? { commit_request_id: "commit-request-browser-journey", repository: journey.repository,
            branch: "fixture-branch", expected_head: journey.head, commit_message: "test: update fixture compose configuration",
            reviewed_files: [journey.file], reviewed_content_fingerprint: "review-browser-fingerprint",
            commit_approval_status: completed || approved ? "approved" : "pending" } : null,
        commit_result: { commit_sha: completed ? journey.commit : null,
            commit_message: completed ? "test: update fixture compose configuration" : null,
            committed_files: completed ? [journey.file] : [], completion_time: completed ? observedAt : null },
    };
}

function completedAudit(): WorkflowAuditResponse {
    return {
        effect_kind: "repository_change",
        workflow_id: journey.workflow, workflow_state: "completed", workflow_source: "candidate",
        validation: { valid: true, failure_code: null, failure_stage: null },
        timeline: (["candidate", "planning", "plan", "workflow", "implementation", "approvals", "execution", "verification", "review", "commit"] as const).map((name) => ({ name, status: "completed" as const })),
        candidate: { status: "completed", candidate_id: journey.candidate, candidate_fingerprint: journey.candidateFingerprint,
            source_recommendation_id: candidate.source_recommendation_id, target_id: candidate.target_id, target_type: candidate.target_type },
        planning: { status: "completed", planning_session_id: journey.session, planning_state: "plan_ready", planning_status: "plan_ready",
            created_at: observedAt, planning_completed_at: observedAt, candidate_plan_id: journey.plan, candidate_plan_fingerprint: journey.planFingerprint },
        plan: { status: "completed", plan_id: journey.plan, candidate_plan_fingerprint: journey.planFingerprint, likely_affected_files: [journey.file] },
        workflow: { status: "completed", workflow_id: journey.workflow, workflow_state: "completed", workflow_source: "candidate" },
        implementation: { status: "completed", implementation_request_id: "implementation-browser-journey", execution_intent: "update-compose-stack",
            tool: "fixture-editor", repository_root: journey.repository, repository_head: journey.head, repository_branch: "fixture-branch",
            working_directory: journey.repository, affected_files: [journey.file], translator_version: "fixture-translator-v1" },
        approvals: { status: "completed", shell: { status: "approved", approval_id: "approval-browser-preparation" }, implementation: { status: "approved", approval_id: "approval-browser-implementation" },
            verification: { status: "approved", approval_id: "approval-browser-verification" }, commit: { status: "approved", approval_id: "approval-browser-commit" } },
        execution: { status: "completed", execution_request_id: "execution-browser-journey", execution_status: "succeeded", changed_files_count: 1,
            changed_files: [journey.file], tool: "fixture-editor", repository: journey.repository },
        verification: { status: "completed", verification_plan_id: "verification-browser-journey", verification_evidence_id: "verification-evidence-browser",
            verification_status: "passed", changed_files_digest: "browser-changed-files-digest", verification_check_ids: ["compose-config"],
            repository_head: journey.head, verification_started_at: observedAt, verification_completed_at: observedAt },
        review: { status: "completed", review_result_id: "review-result-browser", review_report_id: "review-report-browser", review_status: "approved",
            reviewed_content_fingerprint: "review-browser-fingerprint", changed_files: [journey.file] },
        commit: { status: "completed", commit_request_id: "commit-request-browser-journey", reviewed_files: [journey.file],
            reviewed_content_fingerprint: "review-browser-fingerprint", expected_branch: "fixture-branch", expected_head: journey.head,
            commit_message: "test: update fixture compose configuration", commit_sha: journey.commit, committed_files: [journey.file] },
    };
}

export async function installRepositoryJourney(page: Page, reject = false, options: { maintenance?: boolean; baseURL?: string } = {}) {
    const origin = new URL(options.baseURL ?? "http://127.0.0.1:5173").origin;
    const maintenance = options.maintenance === true;
    const maintenancePlan = operationalPlan({ identifier: journey.plan, session_id: journey.session,
        candidate_id: journey.candidate, candidate_fingerprint: journey.candidateFingerprint,
        revalidated_candidate_fingerprint: journey.candidateFingerprint });
    const actionRequest = operationalActionRequest({ request_id: "action-request-browser-journey" });
    const sessionResponse = (ready: boolean): CandidatePlanningResponse => maintenance
        ? { ...planningSession(ready), plan: null, operational_plan: ready ? maintenancePlan : null }
        : planningSession(ready);
    const planningPath = `/candidate-planning/${journey.session}`;
    const workflowPath = `/api/v1/agent/workflows/${journey.workflow}`;
    const expectedWrites: JourneyWrite[] = reject ? [
        { path: `${workflowPath}/implementation-approval`, body: { workflow_id: journey.workflow, decision: "reject" } },
    ] : [
        { path: "/candidate-planning", body: { candidate_id: journey.candidate } },
        { path: `${planningPath}/plan`, body: null },
        { path: `${planningPath}/workflow`, body: null },
        { path: `${planningPath}/implementation`, body: { expected_candidate_fingerprint: journey.candidateFingerprint, expected_plan_fingerprint: journey.planFingerprint } },
        { path: `${workflowPath}/implementation-approval`, body: { workflow_id: journey.workflow, decision: "approve" } },
        { path: `${workflowPath}/resume`, body: null },
        { path: `${workflowPath}/verification-approval`, body: { workflow_id: journey.workflow, decision: "approve" } },
        { path: `${workflowPath}/resume`, body: null },
        { path: `${workflowPath}/commit-approval`, body: { workflow_id: journey.workflow, decision: "approve" } },
        { path: `${workflowPath}/resume`, body: null },
    ];
    if (maintenance && !reject) expectedWrites.splice(6);
    let index = 0;
    let planReady = false;
    let implementationReady = reject;
    let phase: Phase = "implementation";
    let approved = false;
    let repositoryPlanReads = 0;
    const writes: JourneyWrite[] = [];
    const unexpected: string[] = [];
    let nextReadGate: { started: () => void; released: Promise<void> } | null = null;
    await page.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin !== origin) {
            unexpected.push(`External request: ${url.origin}`);
            return route.abort();
        }
        const isAgent = url.pathname === "/agent-api" || url.pathname.startsWith("/agent-api/");
        const isCore = url.pathname === "/api/v1" || url.pathname.startsWith("/api/v1/");
        if (!isAgent && !isCore) {
            if (request.method() !== "GET") {
                unexpected.push(`${request.method()} ${url.pathname}`);
                return route.abort();
            }
            return route.continue();
        }
        const path = isAgent ? url.pathname.slice("/agent-api".length) : url.pathname.slice("/api/v1".length);
        if (request.method() !== "GET") {
            const body: unknown = request.postData() ? request.postDataJSON() : null;
            const expected = expectedWrites[index];
            if (!isAgent || request.method() !== "POST" || !expected || expected.path !== path || !isDeepStrictEqual(body, expected.body)) {
                unexpected.push(`${request.method()} ${path}`);
                return route.fulfill({ status: 409, json: { detail: "Request was outside the exact simulated journey." } });
            }
            writes.push({ path, body }); index += 1;
            if (reject) {
                phase = "rejected";
                return route.fulfill({ json: { workflow_id: journey.workflow, workflow_state: "blocked", implementation_approval_status: "rejected", message: "Rejected in browser fixture." } });
            }
            if (path === "/candidate-planning") return route.fulfill({ json: sessionResponse(false) });
            if (path === `${planningPath}/plan`) { planReady = true; return route.fulfill({ json: sessionResponse(true) }); }
            if (path === `${planningPath}/workflow`) return route.fulfill({ json: shell });
            if (path === `${planningPath}/implementation`) {
                implementationReady = true;
                return route.fulfill({ json: { candidate_planning_session_id: journey.session, workflow_session_id: journey.workflow,
                    translation_status: "implementation_ready", implementation_request_id: "implementation-browser-journey",
                    exact_approval_request_id: "approval-browser-implementation", candidate_fingerprint: journey.candidateFingerprint,
                    plan_fingerprint: journey.planFingerprint, repository_head: maintenance ? null : journey.head, translator_version: "fixture-translator-v1", reason_codes: [], failure: null } });
            }
            if (path.endsWith("/resume")) {
                phase = maintenance ? "completed" : phase === "implementation" ? "verification" : phase === "verification" ? "commit" : "completed";
                approved = false;
                return route.fulfill({ status: 204 });
            }
            approved = true;
            return route.fulfill({ json: { workflow_id: journey.workflow, workflow_state: `awaiting_${phase}_approval`, [`${phase}_approval_status`]: "approved", message: "Approved in browser fixture." } });
        }
        if (isAgent && path === `${planningPath}/workflow`) return route.fulfill({ json: shell });
        if (isCore && path === `/execution-candidates/${journey.candidate}`) return route.fulfill({ json: maintenance
            ? maintenanceCandidate
            : candidate });
        if (isAgent && path === planningPath) return route.fulfill({ json: sessionResponse(planReady) });
        if (isAgent && path === `${planningPath}/plan`) {
            repositoryPlanReads += 1;
            if (!maintenance && planReady) return route.fulfill({ json: plan });
            return route.fulfill({ status: 404, json: { detail: "Repository plan not found." } });
        }
        if (isAgent && path === `${workflowPath}/implementation-request` && implementationReady) {
            const snapshot = maintenance ? maintenanceWorkflow(phase, approved, actionRequest) : workflowDetail(phase, approved);
            const gate = nextReadGate;
            nextReadGate = null;
            if (gate) { gate.started(); await gate.released; }
            return route.fulfill({ json: snapshot });
        }
        if (isAgent && maintenance && path === `${workflowPath}/operational-lifecycle`) {
            const complete = phase === "completed";
            return route.fulfill({ json: operationalLifecycle({
                workflow_id: journey.workflow, workflow_state: complete ? "completed" : "awaiting_implementation_approval",
                candidate_id: journey.candidate, planning_session_id: journey.session,
                candidate_fingerprint: journey.candidateFingerprint, plan_fingerprint: journey.planFingerprint,
                availability: complete ? "complete" : "agent_only", consistency_status: complete ? "consistent" : "agent_only",
                agent_execution_stage: complete ? "verified" : "not_started", core_record_state: complete ? "verified" : null,
                action_request_id: actionRequest.request_id, request_digest: actionRequest.request_digest,
                target_fingerprint: actionRequest.target_fingerprint, observed_target_fingerprint: complete ? actionRequest.target_fingerprint : null,
                target_version: actionRequest.target_version, disruption_scope: actionRequest.disruption_scope,
                request_created_at: actionRequest.generated_at, request_expires_at: actionRequest.expires_at,
                action_approval: { approval_id: "approval-browser-implementation", decision_status: complete || approved ? "approved" : "pending",
                    presentation_state: complete || approved ? "resolved" : "actionable", actionable: !complete && !approved, expires_at: actionRequest.expires_at },
                barrier_crossed: complete, barrier_crossing_count: complete ? 1 : 0,
                provider_operation_captured: complete, provider_operation_capture_count: complete ? 1 : 0,
                dispatch_status: complete ? "succeeded" : null, provider_operation_reference: complete ? "fixture-operation-reference" : null,
                transitions: complete ? [{ sequence: 1, state: "verified", occurred_at: observedAt }] : [],
                verification_status: complete ? "succeeded" : null, observed_state: complete ? "running" : null,
                observed_health: complete ? "healthy" : null, terminal: complete,
            }) });
        }
        if (isAgent && maintenance && path === `${workflowPath}/recovery-diagnostic`) return route.fulfill({ json: operationalDiagnostic({
            applicable: phase === "completed", correlation: { workflow_id: journey.workflow, request_id: actionRequest.request_id,
                request_digest_match: true, agent_record_present: phase === "completed", core_record_present: phase === "completed" },
        }) });
        if (isAgent && path === `${workflowPath}/audit` && phase === "completed") return route.fulfill({ json: {
            ...completedAudit(), effect_kind: maintenance ? "operational_action" : "repository_change",
        } });
        return route.fulfill({ status: 404, json: { detail: "Optional information unavailable in browser fixture." } });
    });
    return { writes, expectedWrites, unexpected, get repositoryPlanReads() { return repositoryPlanReads; }, holdNextWorkflowRead: () => {
        let release!: () => void;
        let started!: () => void;
        const released = new Promise<void>((resolve) => { release = resolve; });
        const requested = new Promise<void>((resolve) => { started = resolve; });
        nextReadGate = { started, released };
        return { requested, release };
    } };
}

export function maintenanceWorkflow(phase: Phase, approved: boolean, request: ReturnType<typeof operationalActionRequest>): WorkflowDetailResponse {
    const complete = phase === "completed";
    return {
        ...workflowDetail(phase, approved), effect_kind: "operational_action",
        repository: null, working_directory: null, affected_files: [], implementation_request: null,
        operational_action_request: request, verification_approval_status: "not_requested", commit_approval_status: "not_requested",
        approval_presentations: [
            { approval_id: "approval-browser-preparation", purpose: "candidate_workflow_shell", decision_status: "approved", presentation_state: "resolved", actionable: false, reason: "Preparation is recorded." },
            { approval_id: "approval-browser-implementation", purpose: "operational_action", decision_status: complete || approved ? "approved" : "pending",
                presentation_state: complete || approved ? "resolved" : "actionable", actionable: !complete && !approved, reason: "Exact action approval is separate from preparation." },
        ],
        timeline: ["Execution Candidate", "Planning Session", "Candidate Plan", "Workflow", "Operational Action Approval", "Execution", "Verification"].map((name, index) => ({
            name, status: complete || index < 4 || (index === 4 && approved) ? "completed" : index === 4 ? "current" : "waiting",
        })),
        execution: { execution_status: null, started_at: null, completed_at: null, result: null, changed_files_count: 0,
            tool: null, working_directory: null, repository: null, changed_files: [], execution_request_id: null },
        verification_plan: { verification_plan_id: null, verifier_version: null, changed_files_digest: null, verification_check_ids: [],
            command_backed_checks: [], working_directory: null, repository: null, verification_status: "not_applicable" },
        verification_evidence: { verification_status: null, completed_time: null, executed_checks: [], check_results: [], repository_head: null, changed_files_digest: null },
        review: { review_result: null, review_status: null, approved: null, evidence_summary: null, changed_files: [], review_fingerprint: null, model_assisted_review: "Not applicable" },
        commit_request: null, commit_result: { commit_sha: null, commit_message: null, committed_files: [], completion_time: null },
    };
}

export function installMaintenanceJourney(page: Page, baseURL?: string) {
    return installRepositoryJourney(page, false, { maintenance: true, baseURL });
}
