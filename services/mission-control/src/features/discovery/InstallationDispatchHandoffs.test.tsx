import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { dispatchHandoffFixture } from "../../test/installationDispatchHandoff";
import { executionRequestFixture } from "../../test/installationExecutionRequest";
import { getInstallationDispatchHandoff, listInstallationDispatchHandoffs, preserveInstallationDispatchHandoff } from "../../api/installationDispatchHandoff";
import type { InstallationDispatchHandoffV1 } from "../../types/installationDispatchHandoff";
import type { InstallationExecutionRequestV1 } from "../../types/installationExecutionRequest";
import { InstallationDispatchHandoffs } from "./InstallationDispatchHandoffs";

vi.mock("../../api/installationDispatchHandoff", () => ({ listInstallationDispatchHandoffs: vi.fn(), getInstallationDispatchHandoff: vi.fn(), preserveInstallationDispatchHandoff: vi.fn(), dispatchHandoffIdempotencyKey: vi.fn(() => "handoff-key") }));
vi.mock("./DeliveryActivationPreflights", () => ({ DeliveryActivationPreflights: () => null }));
vi.mock("./DeliveryEnablements", () => ({ DeliveryEnablements: () => null }));
const handoff = dispatchHandoffFixture as InstallationDispatchHandoffV1;
const request = executionRequestFixture as InstallationExecutionRequestV1;

describe("installation dispatch handoff presentation", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listInstallationDispatchHandoffs).mockResolvedValue([]); });
    it("renders loading, redacted error, empty, and blocked destination states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationDispatchHandoffs).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken={null} />);
        expect(screen.getByText(/loading saved handoff records/i)).toBeInTheDocument(); reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i); view.unmount();
        render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken={null} />);
        expect(await screen.findByText(/no saved handoff records/i)).toBeInTheDocument();
        expect(screen.getByText(/preparing a record does not send work or start installation/i)).toBeInTheDocument();
        expect(screen.getByText(/Home Assistant remains blocked because its deployment artifact and required proof are missing/i)).toBeInTheDocument();
    });
    it("shows a plain saved status and keeps technical evidence and authority details available", async () => {
        vi.mocked(listInstallationDispatchHandoffs).mockResolvedValueOnce([handoff]); vi.mocked(getInstallationDispatchHandoff).mockResolvedValueOnce({ ...handoff, lifecycle_state: "expired" });
        const user = userEvent.setup(); render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken="csrf" />);
        expect(await screen.findByText("Prepared · Not sent to Agent")).toBeInTheDocument();
        await user.click(await screen.findByRole("button", { name: /review handoff record/i }));
        const detail = screen.getByRole("heading", { name: "Handoff record details" }).parentElement!;
        expect(within(detail).getByText(/this record has expired and cannot be renewed or used to start work/i)).toBeInTheDocument();
        await user.click(within(detail).getByText("Technical handoff and evidence details"));
        expect(within(detail).getByText("core_prepared_not_delivered")).toBeInTheDocument();
        expect(within(detail).getByText(handoff.linkage.execution_request_fingerprint.value)).toBeInTheDocument();
        await user.click(within(detail).getByText("Agent admission contract"));
        expect(within(screen.getByLabelText("Contract-only Agent admission shape")).getAllByText("false")).toHaveLength(5);
        await user.click(within(detail).getByText("Authority flags"));
        expect(within(screen.getByLabelText("Fixed-false authority flags")).getAllByText("false")).toHaveLength(5);
        expect(within(detail).getByText(/core keeps one handoff record for each saved request/i)).toBeInTheDocument();
    });
    it("requires exact identity confirmation and only preserves a non-delivering record", async () => {
        vi.mocked(preserveInstallationDispatchHandoff).mockResolvedValueOnce(handoff); const user = userEvent.setup();
        const { container } = render(<InstallationDispatchHandoffs executionRequests={[request]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /prepare handoff record for request/i }));
        expect(preserveInstallationDispatchHandoff).not.toHaveBeenCalled();
        const confirm = screen.getByRole("heading", { name: "Confirm preparing this handoff record" }).parentElement!;
        expect(within(confirm).getByText(/does not send anything to Agent, authorize installation, or start work/i)).toBeInTheDocument();
        expect(confirm).toHaveTextContent(request.linkage.candidate_record_id);
        await user.click(within(confirm).getByText("Verify request identity"));
        expect(within(confirm).getByText(request.execution_request_fingerprint.value)).toBeInTheDocument();
        await user.click(within(confirm).getByRole("button", { name: "Prepare this record" }));
        expect(preserveInstallationDispatchHandoff).toHaveBeenCalledWith({ schema: "installation-dispatch-handoff-create-v1", execution_request_id: request.execution_request_id }, "csrf", "handoff-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" "); expect(labels).not.toMatch(/install now|run|execute|deploy|dispatch|deliver|send to agent|start workflow|rollback/i);
    });
});
