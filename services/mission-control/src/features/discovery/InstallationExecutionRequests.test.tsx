import { render, screen, within } from "@testing-library/react";
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
    it("renders a retryable list error, empty state, and plain unsupported-capability message", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationExecutionRequests).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        vi.mocked(listInstallationExecutionRequests).mockResolvedValueOnce([]);
        const user = userEvent.setup();
        const view = render(<InstallationExecutionRequests intents={[intent]} csrfToken="csrf" evidenceBundles={[{ agent_request: agentRequest, agent_validation: validation }]} />);
        expect(screen.getByText(/checking saved request records/i)).toBeInTheDocument(); reject(new Error("credential /internal/path 10.0.0.1"));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent(/could not load the saved request records/i);
        const details = within(alert).getByText("Technical details").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i);
        await user.click(within(alert).getByRole("button", { name: "Retry request records" }));
        expect(await screen.findByText("No saved request records.")).toBeInTheDocument();
        expect(recordInstallationExecutionRequest).not.toHaveBeenCalled();
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i); view.unmount();
        render(<InstallationExecutionRequests intents={[]} csrfToken={null} />);
        expect(await screen.findByText("No saved request records.")).toBeInTheDocument();
        expect(screen.getByText(/saving a record preserves the exact approved request and validation/i)).toBeInTheDocument();
        expect(screen.getByText(/Atlas cannot install Home Assistant yet because its deployment package and required evidence are missing/i)).toBeInTheDocument();
    });
    it("shows request details plainly and keeps identifiers and authority fields collapsed", async () => {
        vi.mocked(listInstallationExecutionRequests).mockResolvedValueOnce([record]); vi.mocked(getInstallationExecutionRequest).mockResolvedValueOnce({ ...record, lifecycle_state: "expired" });
        const user = userEvent.setup(); render(<InstallationExecutionRequests intents={[]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "View request record" }));
        const detail = screen.getByRole("heading", { name: "Request record details" }).parentElement!;
        expect(within(detail).getByText(/This preserves the operator-submitted request and validation; it does not start work/i)).toBeInTheDocument();
        expect(within(detail).getByText(/This record has expired. It cannot be renewed or used to start work./i)).toBeInTheDocument();
        const technicalDetails = within(detail).getByText("Technical details").closest("details")!;
        expect(technicalDetails).not.toHaveAttribute("open");
        await user.click(within(technicalDetails).getByText("Technical details"));
        expect(within(technicalDetails).getByText("operator_submitted_agent_validation_evidence")).toBeInTheDocument();
        expect(within(technicalDetails).getAllByText("false")).toHaveLength(5);
        expect(within(technicalDetails).getByText(record.linkage.agent_evidence_fingerprint.value)).toBeInTheDocument();
    });
    it("uses two-step confirmation and only records the exact non-executing request", async () => {
        vi.mocked(recordInstallationExecutionRequest).mockResolvedValueOnce(record); const user = userEvent.setup();
        const { container } = render(<InstallationExecutionRequests intents={[intent]} csrfToken="csrf" evidenceBundles={[{ agent_request: agentRequest, agent_validation: validation }]} />);
        await user.click(await screen.findByRole("button", { name: "Review request details" }));
        expect(recordInstallationExecutionRequest).not.toHaveBeenCalled();
        const confirm = screen.getByRole("heading", { name: "Confirm saving this request record" }).parentElement!;
        expect(within(confirm).getByText(/does not contact Agent, send the request, install software, or run work/i)).toBeInTheDocument();
        const technicalDetails = within(confirm).getByText("Technical details").closest("details")!;
        expect(technicalDetails).not.toHaveAttribute("open");
        await user.click(within(confirm).getByRole("button", { name: "Save request record" }));
        expect(recordInstallationExecutionRequest).toHaveBeenCalledWith(expect.objectContaining({ schema: "installation-execution-request-create-v1", candidate_record_id: intent.approved_subject.candidate_record_id, approval_intent_id: intent.approval_intent_id }), "csrf", "execution-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        expect(screen.getByRole("heading", { name: "Request record details" })).toBeInTheDocument();
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" "); expect(labels).not.toMatch(/install now|run|execute|deploy|dispatch|send to agent|start workflow|rollback/i);
    });

    it("checks saved records after an uncertain write without resending", async () => {
        const matching = { ...record, linkage: { ...record.linkage, approval_intent_id: intent.approval_intent_id } };
        vi.mocked(listInstallationExecutionRequests).mockResolvedValueOnce([]).mockResolvedValueOnce([matching]);
        vi.mocked(recordInstallationExecutionRequest).mockRejectedValueOnce(new Error("request outcome unknown"));
        const user = userEvent.setup();
        render(<InstallationExecutionRequests intents={[intent]} csrfToken="csrf" evidenceBundles={[{ agent_request: agentRequest, agent_validation: validation }]} />);
        await user.click(await screen.findByRole("button", { name: "Review request details" }));
        await user.click(screen.getByRole("button", { name: "Save request record" }));
        expect(await screen.findByText(/save result is unknown. Atlas will not send this request again/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review request details" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Check saved records" }));
        expect(await screen.findByText(/Atlas found the saved request record/i)).toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Request record details" })).toBeInTheDocument();
        expect(recordInstallationExecutionRequest).toHaveBeenCalledTimes(1);
        expect(listInstallationExecutionRequests).toHaveBeenCalledTimes(2);
        expect(getInstallationExecutionRequest).not.toHaveBeenCalled();
    });

    it("keeps an absent uncertain write locked after a read check and allows read retries", async () => {
        let rejectList: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationExecutionRequests).mockReturnValueOnce(new Promise((_, reject) => { rejectList = reject; }));
        const failedRead = render(<InstallationExecutionRequests intents={[intent]} csrfToken="csrf" evidenceBundles={[{ agent_request: agentRequest, agent_validation: validation }]} />);
        rejectList(new Error("list unavailable"));
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: "Review request details" })).not.toBeInTheDocument();
        expect(recordInstallationExecutionRequest).not.toHaveBeenCalled();
        failedRead.unmount();

        vi.mocked(listInstallationExecutionRequests).mockResolvedValueOnce([]).mockResolvedValueOnce([]);
        vi.mocked(recordInstallationExecutionRequest).mockRejectedValueOnce(new Error("request outcome unknown"));
        const user = userEvent.setup();
        render(<InstallationExecutionRequests intents={[intent]} csrfToken="csrf" evidenceBundles={[{ agent_request: agentRequest, agent_validation: validation }]} />);
        await user.click(await screen.findByRole("button", { name: "Review request details" }));
        await user.click(screen.getByRole("button", { name: "Save request record" }));
        await screen.findByRole("alert");
        await user.click(screen.getByRole("button", { name: "Check saved records" }));
        expect(await screen.findByText(/No matching request record was found. The previous save is still uncertain/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review request details" })).not.toBeInTheDocument();
        expect(recordInstallationExecutionRequest).toHaveBeenCalledTimes(1);
    });

    it("keeps a failed recovery read safe and hides its technical error until expanded", async () => {
        const matching = { ...record, linkage: { ...record.linkage, approval_intent_id: intent.approval_intent_id } };
        vi.mocked(listInstallationExecutionRequests).mockResolvedValueOnce([]).mockRejectedValueOnce(new Error("temporary list failure")).mockResolvedValueOnce([matching]);
        vi.mocked(recordInstallationExecutionRequest).mockRejectedValueOnce(new Error("request outcome unknown"));
        const user = userEvent.setup();
        const { container } = render(<InstallationExecutionRequests intents={[intent]} csrfToken="csrf" evidenceBundles={[{ agent_request: agentRequest, agent_validation: validation }]} />);
        await user.click(await screen.findByRole("button", { name: "Review request details" }));
        await user.click(screen.getByRole("button", { name: "Save request record" }));
        await screen.findByText(/save result is unknown/i);
        await user.click(screen.getByRole("button", { name: "Check saved records" }));
        expect(await screen.findByText(/Atlas could not check whether the request was saved/i)).toBeInTheDocument();
        const details = screen.getAllByText("Technical details").at(-1)?.closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(within(details as HTMLElement).getByText("Saved request records are currently unavailable.")).not.toBeVisible();
        expect(container).not.toHaveTextContent("temporary list failure");
        expect(screen.queryByRole("button", { name: "Review request details" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Check saved records" }));
        expect(await screen.findByText(/Atlas found the saved request record/i)).toBeInTheDocument();
        expect(recordInstallationExecutionRequest).toHaveBeenCalledTimes(1);
        expect(listInstallationExecutionRequests).toHaveBeenCalledTimes(3);
    });

    it("can retry reading a saved request's details", async () => {
        vi.mocked(listInstallationExecutionRequests).mockResolvedValueOnce([record]);
        vi.mocked(getInstallationExecutionRequest).mockRejectedValueOnce(new Error("temporary read failure")).mockResolvedValueOnce(record);
        const user = userEvent.setup();
        render(<InstallationExecutionRequests intents={[]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "View request record" }));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Request details are unavailable. Try again.");
        expect(within(alert).getByText("Technical details").closest("details")).not.toHaveAttribute("open");
        await user.click(within(alert).getByRole("button", { name: "Retry request details" }));
        expect(await screen.findByRole("heading", { name: "Request record details" })).toBeInTheDocument();
        expect(getInstallationExecutionRequest).toHaveBeenCalledTimes(2);
        expect(recordInstallationExecutionRequest).not.toHaveBeenCalled();
    });
});
