import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createDeliveryActivationPreflight, getDeliveryActivationPreflight, listDeliveryActivationPreflights } from "../../api/deliveryActivationPreflight";
import { deliveryActivationPreflightFixture as fixture } from "../../test/deliveryActivationPreflight";
import { DeliveryActivationPreflights } from "./DeliveryActivationPreflights";

vi.mock("../../api/deliveryActivationPreflight", () => ({ listDeliveryActivationPreflights: vi.fn(), getDeliveryActivationPreflight: vi.fn(), createDeliveryActivationPreflight: vi.fn(), deliveryActivationPreflightIdempotencyKey: vi.fn(() => "preflight-key") }));
describe("delivery activation preflight presentation", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listDeliveryActivationPreflights).mockResolvedValue({ preflights: [], nextCursor: null }); });
    it("renders loading, redacted error, empty, non-activating, freshness, and Home Assistant states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listDeliveryActivationPreflights).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<DeliveryActivationPreflights csrfToken={null} />);
        expect(screen.getByText(/loading delivery activation preflight evidence/i)).toBeInTheDocument(); reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/credential \/internal|10\.0\.0\.1/i); view.unmount();
        render(<DeliveryActivationPreflights csrfToken={null} />);
        expect(await screen.findByText(/no delivery activation preflight evidence records/i)).toBeInTheDocument();
        expect(screen.getByText(/not delivery activation/i)).toBeInTheDocument(); expect(screen.getByText(/at most 30 seconds/i)).toBeInTheDocument(); expect(screen.getByText(/Home Assistant remains blocked, non-installable, and non-executable/i)).toBeInTheDocument();
    });
    it("renders get lifecycle, fingerprints, audit, no-replay, and false authority", async () => {
        vi.mocked(listDeliveryActivationPreflights).mockResolvedValueOnce({ preflights: [fixture], nextCursor: null });
        vi.mocked(getDeliveryActivationPreflight).mockResolvedValueOnce({ ...fixture, status: { ...fixture.status, lifecycle: "expired" }, audit_evidence: { ...fixture.audit_evidence, lifecycle: "expired" } });
        const user = userEvent.setup(); render(<DeliveryActivationPreflights csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review durable preflight evidence/i }));
        const detail = screen.getByRole("heading", { name: /durable local preflight evidence/i }).parentElement!;
        expect(within(detail).getByText(/expired; terminal or unavailable and not activated/i)).toBeInTheDocument();
        expect(within(detail).getAllByText(fixture.result.linkage.simulated_acknowledgement_evidence_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(detail).getAllByText(fixture.audit_evidence.evidence_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(screen.getByLabelText("Fixed-false preflight authority flags")).getAllByText("false")).toHaveLength(11);
        expect(within(detail).getByText(/exact retry returning the original evidence/i)).toBeInTheDocument();
    });
    it("creates only durable evidence after exact confirmation and exposes no prohibited controls", async () => {
        vi.mocked(createDeliveryActivationPreflight).mockResolvedValueOnce(fixture); const user = userEvent.setup();
        const preparation = { schema: "delivery-activation-preflight-create-v1" as const, delivery_preparation_id: fixture.result.delivery_preparation_id, preparation_fingerprint: fixture.result.preparation_fingerprint };
        const { container } = render(<DeliveryActivationPreflights preparations={[preparation]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /create durable preflight evidence only/i }));
        expect(createDeliveryActivationPreflight).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: /confirm durable evidence creation only/i }));
        expect(createDeliveryActivationPreflight).toHaveBeenCalledWith(preparation, "csrf", "preflight-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" ");
        expect(labels).not.toMatch(/activate|send|deliver|run|install|execute|deploy|dispatch|start workflow|rollback/i);
    });
});
