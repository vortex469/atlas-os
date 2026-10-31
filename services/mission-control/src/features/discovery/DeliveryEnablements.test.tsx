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

    it("renders loading, retryable error, empty, expiry, and blocked Home Assistant", async () => {
        let reject: (error: Error) => void = () => undefined;
        vi.mocked(listDeliveryEnablements).mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        const view = render(<DeliveryEnablements csrfToken={null} />);
        expect(screen.getByText(/loading operator delivery enablement evidence/i)).toBeInTheDocument();
        reject(new Error("credential /internal/path 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/couldn’t load saved delivery choices/i));
        expect(view.container).not.toHaveTextContent(/credential \/internal|10\.0\.0\.1/i);
        await userEvent.setup().click(screen.getByRole("button", { name: /try again/i }));
        expect(await screen.findByText(/no delivery choices have been saved/i)).toBeInTheDocument(); view.unmount();
        render(<DeliveryEnablements csrfToken={null} />);
        expect(await screen.findByText(/no delivery choices have been saved/i)).toBeInTheDocument();
        expect(screen.getByText(/does not send, install, or run anything/i)).toBeInTheDocument();
        expect(screen.getByText(/expires with its readiness check, within 30 seconds/i)).toBeInTheDocument();
        expect(screen.getByText(/home assistant can’t be installed or run from atlas yet/i)).toBeInTheDocument();
    });

    it("renders get lifecycle, v0.20-v0.29 fingerprints, audit, no-replay, and fixed false flags", async () => {
        vi.mocked(listDeliveryEnablements).mockResolvedValueOnce({ enablements: [fixture], nextCursor: null });
        vi.mocked(getDeliveryEnablement).mockResolvedValueOnce({ ...fixture, status: { ...fixture.status, lifecycle: "expired" }, audit_evidence: { ...fixture.audit_evidence, lifecycle: "expired" } });
        const user = userEvent.setup(); render(<DeliveryEnablements csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /review details/i }));
        const detail = screen.getByRole("heading", { name: /delivery choice details/i }).parentElement!;
        expect(within(detail).getByText(/this choice has expired and can’t be renewed\. no delivery was sent/i)).toBeInTheDocument();
        expect(within(detail).getByText(/technical details/i).closest("details")).not.toHaveAttribute("open");
        expect(within(detail).getAllByText(fixture.record.linkage.agent_validation_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(detail).getAllByText(fixture.record.linkage.preflight_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(detail).getAllByText(fixture.audit_evidence.evidence_fingerprint.value).length).toBeGreaterThan(0);
        expect(within(screen.getByLabelText("Fixed-false enablement authority flags")).getAllByText("false")).toHaveLength(18);
        expect(within(detail).getByText(/a retry can return only this same record/i)).toBeInTheDocument();
        expect(within(detail).getAllByText(DELIVERY_ENABLEMENT_CONFIRMATION).length).toBeGreaterThan(0);
    });

    it("creates only durable evidence after exact confirmation and exposes no prohibited controls", async () => {
        vi.mocked(createDeliveryEnablement).mockResolvedValueOnce(fixture);
        const candidate = { create: { schema: "operator-controlled-delivery-enablement-create-v1" as const, preflight_id: fixture.record.preflight_id, preflight_fingerprint: fixture.record.preflight_fingerprint, confirmation: DELIVERY_ENABLEMENT_CONFIRMATION }, deliveryPreparationId: fixture.record.delivery_preparation_id, preparationFingerprint: fixture.record.preparation_fingerprint };
        const user = userEvent.setup(); const { container } = render(<DeliveryEnablements candidates={[candidate]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /choose enablement for later review/i }));
        expect(createDeliveryEnablement).not.toHaveBeenCalled();
        const confirmation = screen.getByRole("heading", { name: /save this delivery choice/i }).parentElement!;
        expect(within(confirmation).getByText(new RegExp(DELIVERY_ENABLEMENT_CONFIRMATION.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))).toBeInTheDocument();
        expect(within(confirmation).getByText(fixture.record.delivery_preparation_id)).toBeInTheDocument();
        await user.click(within(confirmation).getByRole("button", { name: /confirm my choice/i }));
        expect(createDeliveryEnablement).toHaveBeenCalledWith(candidate.create, "csrf", "enablement-key");
        expect(container.querySelectorAll("a, form")).toHaveLength(0);
        const labels = Array.from(container.querySelectorAll("button, a")).map((node) => node.textContent).join(" ");
        expect(labels).not.toMatch(/\bsend\b|\bdeliver\b|\bactivate\b|\brun\b|\binstall\b|\bexecute\b|\bdeploy\b|\bdispatch\b|start workflow|\brollback\b/i);
    });

    it("withholds creation until records load and after an uncertain attempt for the same preflight", async () => {
        const candidate = { create: { schema: "operator-controlled-delivery-enablement-create-v1" as const, preflight_id: "new-preflight", preflight_fingerprint: fixture.record.preflight_fingerprint, confirmation: DELIVERY_ENABLEMENT_CONFIRMATION }, deliveryPreparationId: "new-preparation", preparationFingerprint: fixture.record.preparation_fingerprint };
        let rejectList: (error: Error) => void = () => undefined;
        vi.mocked(listDeliveryEnablements).mockReturnValueOnce(new Promise((_, reject) => { rejectList = reject; }));
        const failedRead = render(<DeliveryEnablements candidates={[candidate]} csrfToken="csrf" />);
        rejectList(new Error("list unavailable"));
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: /choose enablement for later review/i })).not.toBeInTheDocument();
        await userEvent.setup().click(screen.getByRole("button", { name: /try again/i }));
        expect(await screen.findByRole("button", { name: /choose enablement for later review/i })).toBeInTheDocument();
        failedRead.unmount();

        vi.mocked(listDeliveryEnablements).mockResolvedValueOnce({ enablements: [fixture], nextCursor: null });
        vi.mocked(createDeliveryEnablement).mockRejectedValueOnce(new Error("request outcome unknown"));
        vi.mocked(getDeliveryEnablement).mockResolvedValueOnce(fixture);
        const user = userEvent.setup();
        render(<DeliveryEnablements candidates={[candidate]} csrfToken="csrf" />);
        await user.click(await screen.findByRole("button", { name: /choose enablement for later review/i }));
        await user.click(screen.getByRole("button", { name: /confirm my choice/i }));
        await screen.findByRole("alert");
        expect(screen.queryByRole("heading", { name: /save this delivery choice/i })).not.toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent(/couldn’t confirm whether it saved this choice/i);
        expect(screen.queryByRole("button", { name: /choose enablement for later review/i })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /reload records/i }));
        await waitFor(() => expect(listDeliveryEnablements).toHaveBeenCalledTimes(4));
        expect(screen.queryByRole("button", { name: /choose enablement for later review/i })).not.toBeInTheDocument();
    });
});
