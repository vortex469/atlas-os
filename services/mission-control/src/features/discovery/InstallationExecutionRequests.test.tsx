import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { executionRequestFixture } from "../../test/installationExecutionRequest";
import { getInstallationExecutionRequest, listInstallationExecutionRequests, recordInstallationExecutionRequest } from "../../api/installationExecutionRequest";
import type { InstallationApprovalIntentV1 } from "../../types/installationApprovalIntent";
import type { AgentInstallContainerRequestV1, InstallationExecutionRequestV1 } from "../../types/installationExecutionRequest";
import type { InstallContainerValidation } from "../../types/atlasAgent";
import { InstallationExecutionRequests } from "./InstallationExecutionRequests";

vi.mock("../../api/installationExecutionRequest", () => ({ listInstallationExecutionRequests: vi.fn(), getInstallationExecutionRequest: vi.fn(), recordInstallationExecutionRequest: vi.fn(), executionRequestIdempotencyKey: vi.fn(() => "execution-key") }));
vi.mock("./InstallationDispatchHandoffs", () => ({ InstallationDispatchHandoffs: () => null }));
const record = executionRequestFixture as InstallationExecutionRequestV1;
const intent = { schema: "installation-approval-intent-v1", approval_intent_id: record.linkage.approval_intent_id, operator_id: "operator-a", recorded_at: record.recorded_at, approved_subject: { candidate_record_id: record.linkage.candidate_record_id, candidate_envelope_fingerprint: "a".repeat(64), admission_fingerprint: "b".repeat(64), candidate_record_fingerprint: "c".repeat(64) }, statement: "operator_approved_exact_non_executable_candidate", intent_fingerprint: "d".repeat(64) } satisfies InstallationApprovalIntentV1;
const agentRequest = { schema: "agent-install-container-request-v1", operation: "install-container", mode: "validate-only", request_id: record.linkage.agent_request_id, issued_at: record.recorded_at, expires_at: record.valid_until, subject: {}, approval: { candidate_record_id: record.linkage.candidate_record_id, approval_intent_id: record.linkage.approval_intent_id }, artifact: {}, limits: {}, request_fingerprint: record.linkage.agent_request_fingerprint } satisfies AgentInstallContainerRequestV1;
const validation = { schema: "agent-install-container-validation-v1", request_id: agentRequest.request_id, request_fingerprint: record.linkage.agent_request_fingerprint, validated_at: record.recorded_at, status: "valid_but_unsupported", reason_codes: [], execution_supported: false, dispatch_allowed: false, mutation_allowed: false, replay_allowed: false, validation_fingerprint: record.linkage.agent_validation_fingerprint, evidence: { evidence_schema: "agent-install-container-audit-evidence-v1", request_id: agentRequest.request_id, request_fingerprint: record.linkage.agent_request_fingerprint, approval: {} as never, subject: {} as never, artifact_kind: "single-oci-container-v1", source_plan_fingerprint: record.linkage.source_plan_fingerprint, source_repository_path: "redacted.yaml", source_service: "redacted", source_content_digest: `sha256:${"6".repeat(64)}`, image_digest: `sha256:${"7".repeat(64)}`, runtime_limit_policy_fingerprint: record.linkage.artifact_policy_fingerprint, validated_at: record.recorded_at, status: "valid_but_unsupported", reason_codes: [], execution_supported: false, dispatch_allowed: false, mutation_allowed: false, replay_allowed: false, evidence_fingerprint: record.linkage.agent_evidence_fingerprint } } satisfies InstallContainerValidation;

describe("installation execution request presentation", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listInstallationExecutionRequests).mockResolvedValue([]); });
    it("renders loading, redacted error, empty, default-disabled, and Home Assistant states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationExecutionRequests).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<InstallationExecutionRequests intents={[]} csrfToken={null} />);
        expect(screen.getByText(/loading execution request records/i)).toBeInTheDocument(); reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i); view.unmount();
        render(<InstallationExecutionRequests intents={[]} csrfToken={null} />);
        expect(await screen.findByText(/no installation execution request records/i)).toBeInTheDocument();
        expect(screen.getByText(/default-disabled and non-authorizing/i)).toBeInTheDocument(); expect(screen.getByText(/Home Assistant remains blocked and non-executable/i)).toBeInTheDocument();
    });
    it("lists and gets lifecycle, expiry, fingerprints, evidence, replay posture, and fixed-false authority", async () => {
        vi.mocked(listInstallationExecutionRequests).mockResolvedValueOnce([record]); vi.mocked(getInstallationExecutionRequest).mockResolvedValueOnce({ ...record, lifecycle_state: "expired" });
        const user = userEvent.setup(); render(<InstallationExecutionRequests intents={[]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review immutable request record/i }));
        const detail = screen.getByRole("heading", { name: /immutable non-executing request evidence/i }).parentElement!;
        expect(within(detail).getByText("expired terminally; no renewal, replay, or work")).toBeInTheDocument();
        expect(within(detail).getByText("operator_submitted_agent_validation_evidence")).toBeInTheDocument();
        expect(within(detail).getAllByText("false")).toHaveLength(5); expect(within(detail).getByText(record.linkage.agent_evidence_fingerprint.value)).toBeInTheDocument();
    });
    it("requires exact evidence confirmation and calls only record preservation", async () => {
        vi.mocked(recordInstallationExecutionRequest).mockResolvedValueOnce(record); const user = userEvent.setup();
        const { container } = render(<InstallationExecutionRequests intents={[intent]} csrfToken="csrf" evidenceBundles={[{ agent_request: agentRequest, agent_validation: validation }]} />);
        await user.click(await screen.findByRole("button", { name: /preserve non-executing execution request record only/i }));
        expect(recordInstallationExecutionRequest).not.toHaveBeenCalled();
        const confirm = screen.getByRole("heading", { name: /confirm preservation/i }).parentElement!; expect(within(confirm).getByText(/grants no authority and starts no work/i)).toBeInTheDocument();
        await user.click(within(confirm).getByRole("button", { name: /confirm record preservation only/i }));
        expect(recordInstallationExecutionRequest).toHaveBeenCalledWith(expect.objectContaining({ schema: "installation-execution-request-create-v1", candidate_record_id: intent.approved_subject.candidate_record_id, approval_intent_id: intent.approval_intent_id }), "csrf", "execution-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" "); expect(labels).not.toMatch(/install now|run|execute|deploy|dispatch|send to agent|start workflow|rollback/i);
    });
});
