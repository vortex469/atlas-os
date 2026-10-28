import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createDeliveryEnablement, getDeliveryEnablement, listDeliveryEnablements } from "../../api/deliveryEnablement";
import { deliveryEnablementFixture as fixture } from "../../test/deliveryEnablement";
import { DELIVERY_ENABLEMENT_CONFIRMATION } from "../../types/deliveryEnablement";
import { DeliveryEnablements } from "./DeliveryEnablements";

vi.mock("../../api/deliveryEnablement", () => ({ listDeliveryEnablements: vi.fn(), getDeliveryEnablement: vi.fn(), createDeliveryEnablement: vi.fn(), deliveryEnablementIdempotencyKey: vi.fn(() => "enablement-key") }));

describe("operator delivery enablement presentation", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listDeliveryEnablements).mockResolvedValue({ enablements: [], nextCursor: null }); });

    it("renders loading, redacted error, empty, and blocked destination states", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listDeliveryEnablements).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<DeliveryEnablements csrfToken={null} />);
        expect(screen.getByText(/loading saved choices/i)).toBeInTheDocument();
        reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/credential \/internal|10\.0\.0\.1/i); view.unmount();
        render(<DeliveryEnablements csrfToken={null} />);
        expect(await screen.findByText(/no choices saved yet/i)).toBeInTheDocument();
        expect(screen.getByText(/saving a choice does not turn delivery on/i)).toBeInTheDocument();
        expect(screen.getByText(/expires with its readiness check, within 30 seconds/i)).toBeInTheDocument();
        expect(screen.getByText(/Home Assistant remains blocked because its deployment artifact and required proof are missing/i)).toBeInTheDocument();
    });

    it("shows a plain saved outcome and keeps technical lineage and authority details available", async () => {
        vi.mocked(listDeliveryEnablements).mockResolvedValueOnce({ enablements: [fixture], nextCursor: null });
        vi.mocked(getDeliveryEnablement).mockResolvedValueOnce({ ...fixture, status: { ...fixture.status, lifecycle: "expired" }, audit_evidence: { ...fixture.audit_evidence, lifecycle: "expired" } });
        const user = userEvent.setup(); render(<DeliveryEnablements csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review saved choice/i }));
        const detail = screen.getByRole("heading", { name: "Saved choice details" }).parentElement!;
        expect(within(detail).getByText(/expired\. delivery is still off/i)).toBeInTheDocument();
        expect(within(detail).getAllByText(/does not send, install, or execute anything/i).length).toBeGreaterThan(0);
        await user.click(within(detail).getByText("Choice and evidence details"));
        expect(within(detail).getAllByText(fixture.record.linkage.agent_validation_fingerprint.value).length).toBeGreaterThan(0);
        await user.click(within(detail).getByText("Earlier evidence linked to this choice"));
        expect(within(detail).getAllByText(fixture.record.linkage.preflight_fingerprint.value).length).toBeGreaterThan(0);
        await user.click(within(detail).getByText("Audit record"));
        expect(within(detail).getAllByText(fixture.audit_evidence.evidence_fingerprint.value).length).toBeGreaterThan(0);
        await user.click(within(detail).getByText("Authority flags"));
        expect(within(screen.getByLabelText("Fixed-false enablement authority flags")).getAllByText("false")).toHaveLength(18);
        expect(within(detail).getByText(/saving the same choice again returns the original record/i)).toBeInTheDocument();
        expect(within(detail).getAllByText(DELIVERY_ENABLEMENT_CONFIRMATION).length).toBeGreaterThan(0);
    });

    it("creates only durable evidence after exact confirmation and exposes no prohibited controls", async () => {
        vi.mocked(createDeliveryEnablement).mockResolvedValueOnce(fixture);
        const candidate = { create: { schema: "operator-controlled-delivery-enablement-create-v1" as const, preflight_id: fixture.record.preflight_id, preflight_fingerprint: fixture.record.preflight_fingerprint, confirmation: DELIVERY_ENABLEMENT_CONFIRMATION }, deliveryPreparationId: fixture.record.delivery_preparation_id, preparationFingerprint: fixture.record.preparation_fingerprint };
        const user = userEvent.setup(); const { container } = render(<DeliveryEnablements candidates={[candidate]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: "Save choice for later review" }));
        expect(createDeliveryEnablement).not.toHaveBeenCalled();
        const confirmation = screen.getByRole("heading", { name: "Confirm this saved choice" }).parentElement!;
        expect(within(confirmation).getByText(new RegExp(DELIVERY_ENABLEMENT_CONFIRMATION.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))).toBeInTheDocument();
        expect(confirmation).toHaveTextContent(fixture.record.delivery_preparation_id);
        await user.click(within(confirmation).getByText("Verify readiness and preparation fingerprints"));
        expect(within(confirmation).getByText(fixture.record.preparation_fingerprint.value)).toBeInTheDocument();
        await user.click(within(confirmation).getByRole("button", { name: "Save this choice" }));
        expect(createDeliveryEnablement).toHaveBeenCalledWith(candidate.create, "csrf", "enablement-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" ");
        expect(labels).not.toMatch(/\bsend\b|\bdeliver\b|\bactivate\b|\brun\b|\binstall\b|\bexecute\b|\bdeploy\b|\bdispatch\b|start workflow|\brollback\b/i);
    });
});
