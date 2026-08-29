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
const handoff = dispatchHandoffFixture as InstallationDispatchHandoffV1;
const request = executionRequestFixture as InstallationExecutionRequestV1;

describe("installation dispatch handoff presentation", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listInstallationDispatchHandoffs).mockResolvedValue([]); });
    it("renders loading, redacted error, empty, default-disabled, and Home Assistant states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationDispatchHandoffs).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken={null} />);
        expect(screen.getByText(/loading dispatch handoff records/i)).toBeInTheDocument(); reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i); view.unmount();
        render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken={null} />);
        expect(await screen.findByText(/no installation dispatch handoff records/i)).toBeInTheDocument();
        expect(screen.getByText(/default-disabled and non-authorizing/i)).toBeInTheDocument(); expect(screen.getByText(/Home Assistant remains blocked and non-executable/i)).toBeInTheDocument();
    });
    it("lists and gets lifecycle, expiry, linkage, Agent contract, audit, replay, and fixed-false authority", async () => {
        vi.mocked(listInstallationDispatchHandoffs).mockResolvedValueOnce([handoff]); vi.mocked(getInstallationDispatchHandoff).mockResolvedValueOnce({ ...handoff, lifecycle_state: "expired" });
        const user = userEvent.setup(); render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review immutable handoff record/i }));
        const detail = screen.getByRole("heading", { name: /immutable non-delivering handoff evidence/i }).parentElement!;
        expect(within(detail).getByText(/expired terminally; no renew, retry, replay, delivery, or work/i)).toBeInTheDocument();
        expect(within(detail).getByText("core_prepared_not_delivered")).toBeInTheDocument(); expect(within(detail).getByText(/valid_but_not_admitted/i)).toBeInTheDocument();
        expect(within(screen.getByLabelText("Fixed-false authority flags")).getAllByText("false")).toHaveLength(5);
        expect(within(screen.getByLabelText("Contract-only Agent admission shape")).getAllByText("false")).toHaveLength(5); expect(within(detail).getByText(handoff.linkage.execution_request_fingerprint.value)).toBeInTheDocument();
        expect(within(detail).getByText(/one execution request can produce at most one envelope forever/i)).toBeInTheDocument();
    });
    it("requires exact identity confirmation and only preserves a non-delivering record", async () => {
        vi.mocked(preserveInstallationDispatchHandoff).mockResolvedValueOnce(handoff); const user = userEvent.setup();
        const { container } = render(<InstallationDispatchHandoffs executionRequests={[request]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /preserve non-delivering handoff record only/i }));
        expect(preserveInstallationDispatchHandoff).not.toHaveBeenCalled();
        const confirm = screen.getByRole("heading", { name: /confirm preservation/i }).parentElement!; expect(within(confirm).getByText(/does not deliver, invoke Agent, admit work, authorize execution, or permit replay/i)).toBeInTheDocument();
        await user.click(within(confirm).getByRole("button", { name: /confirm handoff record preservation only/i }));
        expect(preserveInstallationDispatchHandoff).toHaveBeenCalledWith({ schema: "installation-dispatch-handoff-create-v1", execution_request_id: request.execution_request_id }, "csrf", "handoff-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" "); expect(labels).not.toMatch(/install now|run|execute|deploy|dispatch|deliver|send to agent|start workflow|rollback/i);
    });
});
