import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createDeliveryActivationPreflight, getDeliveryActivationPreflight, listDeliveryActivationPreflights } from "../../api/deliveryActivationPreflight";
import { deliveryActivationPreflightFixture as fixture } from "../../test/deliveryActivationPreflight";
import { DeliveryActivationPreflights } from "./DeliveryActivationPreflights";

vi.mock("../../api/deliveryActivationPreflight", () => ({ listDeliveryActivationPreflights: vi.fn(), getDeliveryActivationPreflight: vi.fn(), createDeliveryActivationPreflight: vi.fn(), deliveryActivationPreflightIdempotencyKey: vi.fn(() => "preflight-key") }));
describe("delivery activation preflight presentation", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listDeliveryActivationPreflights).mockResolvedValue({ preflights: [], nextCursor: null }); });
    it("renders loading, retryable error, empty, expiration, and Home Assistant states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listDeliveryActivationPreflights).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<DeliveryActivationPreflights csrfToken={null} />);
        expect(screen.getByText(/loading delivery activation preflight evidence/i)).toBeInTheDocument(); reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/couldn’t load saved readiness checks/i));
        expect(view.container).not.toHaveTextContent(/credential \/internal|10\.0\.0\.1/i);
        await userEvent.setup().click(screen.getByRole("button", { name: /try again/i }));
        expect(await screen.findByText(/no readiness checks have been saved/i)).toBeInTheDocument(); view.unmount();
        render(<DeliveryActivationPreflights csrfToken={null} />);
        expect(await screen.findByText(/no readiness checks have been saved/i)).toBeInTheDocument();
        expect(screen.getByText(/does not approve, enable, or send delivery/i)).toBeInTheDocument();
        expect(screen.getByText(/expire after 30 seconds or when the saved setup expires/i)).toBeInTheDocument();
        expect(screen.getByText(/home assistant isn’t available for installation through atlas yet/i)).toBeInTheDocument();
    });
    it("renders get lifecycle, fingerprints, audit, no-replay, and false authority", async () => {
        vi.mocked(listDeliveryActivationPreflights).mockResolvedValueOnce({ preflights: [fixture], nextCursor: null });
        vi.mocked(getDeliveryActivationPreflight).mockResolvedValueOnce({ ...fixture, status: { ...fixture.status, lifecycle: "expired" }, audit_evidence: { ...fixture.audit_evidence, lifecycle: "expired" } });
        const user = userEvent.setup(); render(<DeliveryActivationPreflights csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review details/i }));
        const detail = screen.getByRole("heading", { name: /readiness check details/i }).parentElement!;
        expect(within(detail).getByText(/this check has expired and can’t be refreshed\. no delivery was sent/i)).toBeInTheDocument();
        expect(within(detail).getByText(/technical details/i).closest("details")).not.toHaveAttribute("open");
        expect(within(detail).getAllByText(fixture.result.linkage.simulated_acknowledgement_evidence_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(detail).getAllByText(fixture.audit_evidence.evidence_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(screen.getByLabelText("Fixed-false preflight authority flags")).getAllByText("false")).toHaveLength(11);
        expect(within(detail).getByText(/a retry can return only the same saved check/i)).toBeInTheDocument();
    });
    it("creates only durable evidence after exact confirmation and exposes no prohibited controls", async () => {
        vi.mocked(createDeliveryActivationPreflight).mockResolvedValueOnce(fixture); const user = userEvent.setup();
        const preparation = { schema: "delivery-activation-preflight-create-v1" as const, delivery_preparation_id: fixture.result.delivery_preparation_id, preparation_fingerprint: fixture.result.preparation_fingerprint };
        const { container } = render(<DeliveryActivationPreflights preparations={[preparation]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /check readiness/i }));
        expect(createDeliveryActivationPreflight).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: /confirm readiness check/i }));
        expect(createDeliveryActivationPreflight).toHaveBeenCalledWith(preparation, "csrf", "preflight-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" ");
        expect(labels).not.toMatch(/activate|send|deliver|run|install|execute|deploy|dispatch|start workflow|rollback/i);
    });
    it("withholds creation until records load and after an uncertain attempt for the same preparation", async () => {
        const preparation = { schema: "delivery-activation-preflight-create-v1" as const, delivery_preparation_id: "new-preparation", preparation_fingerprint: fixture.result.preparation_fingerprint };
        let rejectList: (error: Error) => void = () => undefined;
        vi.mocked(listDeliveryActivationPreflights).mockReturnValueOnce(new Promise((_, reject) => { rejectList = reject; }));
        const failedRead = render(<DeliveryActivationPreflights preparations={[preparation]} csrfToken="csrf" />);
        rejectList(new Error("list unavailable"));
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: /check readiness/i })).not.toBeInTheDocument();
        failedRead.unmount();

        vi.mocked(listDeliveryActivationPreflights).mockResolvedValueOnce({ preflights: [fixture], nextCursor: null });
        vi.mocked(createDeliveryActivationPreflight).mockRejectedValueOnce(new Error("request outcome unknown"));
        vi.mocked(getDeliveryActivationPreflight).mockResolvedValueOnce(fixture);
        const user = userEvent.setup();
        render(<DeliveryActivationPreflights preparations={[preparation]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /check readiness/i }));
        await user.click(screen.getByRole("button", { name: /confirm readiness check/i }));
        await screen.findByRole("alert");
        expect(screen.queryByRole("heading", { name: /check delivery readiness/i })).not.toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent(/couldn’t confirm whether it saved this check/i);
        expect(screen.queryByRole("button", { name: /check readiness/i })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /reload records/i }));
        await waitFor(() => expect(listDeliveryActivationPreflights).toHaveBeenCalledTimes(3));
        expect(screen.queryByRole("button", { name: /check readiness/i })).not.toBeInTheDocument();
    });
});
