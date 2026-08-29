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

    it("renders loading, redacted error, empty, posture, freshness, and blocked Home Assistant", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listDeliveryEnablements).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<DeliveryEnablements csrfToken={null} />);
        expect(screen.getByText(/loading operator delivery enablement evidence/i)).toBeInTheDocument();
        reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
        expect(view.container).not.toHaveTextContent(/credential \/internal|10\.0\.0\.1/i); view.unmount();
        render(<DeliveryEnablements csrfToken={null} />);
        expect(await screen.findByText(/no operator delivery enablement evidence records/i)).toBeInTheDocument();
        expect(screen.getByText(/operator enabled does not mean activated/i)).toBeInTheDocument();
        expect(screen.getByText(/unused portion of its 30-second maximum window/i)).toBeInTheDocument();
        expect(screen.getByText(/Home Assistant remains blocked, non-installable, and non-executable/i)).toBeInTheDocument();
    });

    it("renders get lifecycle, v0.20-v0.29 fingerprints, audit, no-replay, and fixed false flags", async () => {
        vi.mocked(listDeliveryEnablements).mockResolvedValueOnce({ enablements: [fixture], nextCursor: null });
        vi.mocked(getDeliveryEnablement).mockResolvedValueOnce({ ...fixture, status: { ...fixture.status, lifecycle: "expired" }, audit_evidence: { ...fixture.audit_evidence, lifecycle: "expired" } });
        const user = userEvent.setup(); render(<DeliveryEnablements csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review durable enablement evidence/i }));
        const detail = screen.getByRole("heading", { name: /durable operator enablement evidence only/i }).parentElement!;
        expect(within(detail).getByText(/expired; terminal or unavailable and never delivery authority/i)).toBeInTheDocument();
        expect(within(detail).getAllByText(fixture.record.linkage.agent_validation_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(detail).getAllByText(fixture.record.linkage.preflight_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(detail).getAllByText(fixture.audit_evidence.evidence_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(screen.getByLabelText("Fixed-false enablement authority flags")).getAllByText("false")).toHaveLength(18);
        expect(within(detail).getByText(/expiry never releases it/i)).toBeInTheDocument();
        expect(within(detail).getAllByText(DELIVERY_ENABLEMENT_CONFIRMATION).length).toBeGreaterThan(0);
    });

    it("creates only durable evidence after exact confirmation and exposes no prohibited controls", async () => {
        vi.mocked(createDeliveryEnablement).mockResolvedValueOnce(fixture);
        const candidate = { create: { schema: "operator-controlled-delivery-enablement-create-v1" as const, preflight_id: fixture.record.preflight_id, preflight_fingerprint: fixture.record.preflight_fingerprint, confirmation: DELIVERY_ENABLEMENT_CONFIRMATION }, deliveryPreparationId: fixture.record.delivery_preparation_id, preparationFingerprint: fixture.record.preparation_fingerprint };
        const user = userEvent.setup(); const { container } = render(<DeliveryEnablements candidates={[candidate]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /enable exact delivery for later consideration only/i }));
        expect(createDeliveryEnablement).not.toHaveBeenCalled();
        const confirmation = screen.getByRole("heading", { name: /create durable operator enablement evidence only/i }).parentElement!;
        expect(within(confirmation).getByText(new RegExp(DELIVERY_ENABLEMENT_CONFIRMATION.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))).toBeInTheDocument();
        expect(within(confirmation).getByText(fixture.record.delivery_preparation_id)).toBeInTheDocument();
        await user.click(within(confirmation).getByRole("button", { name: /confirm durable operator enablement evidence only/i }));
        expect(createDeliveryEnablement).toHaveBeenCalledWith(candidate.create, "csrf", "enablement-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" ");
        expect(labels).not.toMatch(/\bsend\b|\bdeliver\b|\bactivate\b|\brun\b|\binstall\b|\bexecute\b|\bdeploy\b|\bdispatch\b|start workflow|\brollback\b/i);
    });
});
