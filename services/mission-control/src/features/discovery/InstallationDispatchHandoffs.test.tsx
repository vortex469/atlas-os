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
    it("renders loading, a retryable load error, empty, and Home Assistant states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationDispatchHandoffs).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<InstallationDispatchHandoffs executionRequests={[request]} csrfToken="csrf" />);
        expect(screen.getByText(/loading dispatch handoff records/i)).toBeInTheDocument(); reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/couldn’t load saved handoff records/i));
        expect(screen.queryByRole("button", { name: /save handoff record/i })).not.toBeInTheDocument();
        expect(view.container).not.toHaveTextContent(/credential|internal\/path|10\.0\.0\.1/i);
        await userEvent.setup().click(screen.getByRole("button", { name: /try again/i }));
        expect(await screen.findByText(/no handoff records have been saved/i)).toBeInTheDocument(); view.unmount();
        render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken={null} />);
        expect(await screen.findByText(/no handoff records have been saved/i)).toBeInTheDocument();
        expect(screen.getByText(/home assistant cannot be installed or run from atlas yet/i)).toBeInTheDocument();
    });
    it("lists and gets lifecycle, expiry, linkage, Agent contract, audit, replay, and fixed-false authority", async () => {
        vi.mocked(listInstallationDispatchHandoffs).mockResolvedValueOnce([handoff]); vi.mocked(getInstallationDispatchHandoff).mockResolvedValueOnce({ ...handoff, lifecycle_state: "expired" });
        const user = userEvent.setup(); render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review record/i }));
        const detail = screen.getByRole("heading", { name: /handoff record details/i }).parentElement!;
        expect(within(detail).getByText(/this record has expired\. it can’t be reused, and no work was started/i)).toBeInTheDocument();
        expect(within(detail).getByText(/technical details/i).closest("details")).not.toHaveAttribute("open");
        expect(within(detail).getByText("core_prepared_not_delivered")).toBeInTheDocument(); expect(within(detail).getByText(/valid_but_not_admitted/i)).toBeInTheDocument();
        expect(within(screen.getByLabelText("Fixed-false authority flags")).getAllByText("false")).toHaveLength(5);
        expect(within(screen.getByLabelText("Contract-only Agent admission shape")).getAllByText("false")).toHaveLength(5); expect(within(detail).getByText(handoff.linkage.execution_request_fingerprint.value)).toBeInTheDocument();
        expect(within(detail).getByText(/one execution request can produce at most one handoff record/i)).toBeInTheDocument();
    });
    it("requires confirmation and only saves a non-delivering record", async () => {
        vi.mocked(preserveInstallationDispatchHandoff).mockResolvedValueOnce(handoff); const user = userEvent.setup();
        const { container } = render(<InstallationDispatchHandoffs executionRequests={[request]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /save handoff record/i }));
        expect(preserveInstallationDispatchHandoff).not.toHaveBeenCalled();
        const confirm = screen.getByRole("heading", { name: /save this handoff record/i }).parentElement!; expect(within(confirm).getByText(/nothing will be sent to agent and no work will start/i)).toBeInTheDocument();
        await user.click(within(confirm).getByRole("button", { name: /save record/i }));
        expect(preserveInstallationDispatchHandoff).toHaveBeenCalledWith({ schema: "installation-dispatch-handoff-create-v1", execution_request_id: request.execution_request_id }, "csrf", "handoff-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" "); expect(labels).not.toMatch(/install now|run|execute|deploy|dispatch|deliver|send to agent|start workflow|rollback/i);
    });

    it("keeps the record list available when one record fails to load and allows a retry", async () => {
        vi.mocked(listInstallationDispatchHandoffs).mockResolvedValueOnce([handoff]);
        vi.mocked(getInstallationDispatchHandoff).mockRejectedValueOnce(new Error("private path"));
        vi.mocked(getInstallationDispatchHandoff).mockResolvedValueOnce(handoff);
        const user = userEvent.setup();
        render(<InstallationDispatchHandoffs executionRequests={[]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review record/i }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/couldn’t load this handoff record/i);
        expect(screen.getByRole("button", { name: /review record/i })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /try again/i }));
        expect(await screen.findByRole("heading", { name: /handoff record details/i })).toBeInTheDocument();
    });

    it("withholds handoff preservation until records load and after an uncertain attempt for the same request", async () => {
        const otherRequest = { ...request, execution_request_id: "00000000-0000-4000-8000-000000000099" };
        let rejectList: (error: Error) => void = () => undefined;
        vi.mocked(listInstallationDispatchHandoffs).mockReturnValueOnce(new Promise((_, reject) => { rejectList = reject; }));
        const failedRead = render(<InstallationDispatchHandoffs executionRequests={[otherRequest]} csrfToken="csrf" />);
        rejectList(new Error("list unavailable"));
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: /save handoff record/i })).not.toBeInTheDocument();
        await userEvent.setup().click(screen.getByRole("button", { name: /try again/i }));
        expect(await screen.findByRole("button", { name: /save handoff record/i })).toBeInTheDocument();
        failedRead.unmount();

        vi.mocked(listInstallationDispatchHandoffs).mockResolvedValueOnce([handoff]);
        vi.mocked(preserveInstallationDispatchHandoff).mockRejectedValueOnce(new Error("request outcome unknown"));
        vi.mocked(getInstallationDispatchHandoff).mockResolvedValueOnce(handoff);
        const user = userEvent.setup();
        render(<InstallationDispatchHandoffs executionRequests={[otherRequest]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /save handoff record/i }));
        await user.click(screen.getByRole("button", { name: /save record/i }));
        await screen.findByRole("alert");
        expect(screen.queryByRole("heading", { name: /save this handoff record/i })).not.toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent(/couldn’t confirm whether it saved this record/i);
        await user.click(screen.getByRole("button", { name: /reload records/i }));
        await waitFor(() => expect(listInstallationDispatchHandoffs).toHaveBeenCalledTimes(4));
        expect(screen.queryByRole("button", { name: /save handoff record/i })).not.toBeInTheDocument();
    });
});
