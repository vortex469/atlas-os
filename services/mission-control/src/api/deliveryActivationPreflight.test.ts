import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { createDeliveryActivationPreflight, getDeliveryActivationPreflight, listDeliveryActivationPreflights, parseDeliveryActivationPreflight } from "./deliveryActivationPreflight";
import { deliveryActivationPreflightFixture as fixture } from "../test/deliveryActivationPreflight";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));
describe("delivery activation preflight API", () => {
    beforeEach(() => vi.resetAllMocks());
    it("strictly parses freshness, linkage, audit, and fixed-false authority", () => {
        expect(parseDeliveryActivationPreflight(fixture)).toEqual(fixture);
        expect(() => parseDeliveryActivationPreflight({ ...fixture, raw_provider_payload: "secret /internal/path 10.0.0.1" })).toThrow(/invalid/i);
        expect(() => parseDeliveryActivationPreflight({ ...fixture, result: { ...fixture.result, delivery_activated: true } })).toThrow(/invalid/i);
        expect(() => parseDeliveryActivationPreflight({ ...fixture, result: { ...fixture.result, expires_at: "2026-08-29T12:00:31Z" } })).toThrow(/invalid/i);
        expect(() => parseDeliveryActivationPreflight({ ...fixture, audit_evidence: { ...fixture.audit_evidence, command: "forbidden" } })).toThrow(/invalid/i);
    });
    it("uses only guarded create, list, and get", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { preflights: [fixture], next_cursor: null } }).mockResolvedValueOnce({ data: fixture });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: fixture });
        await listDeliveryActivationPreflights(); await getDeliveryActivationPreflight("id/unsafe");
        const body = { schema: "delivery-activation-preflight-create-v1" as const, delivery_preparation_id: fixture.result.delivery_preparation_id, preparation_fingerprint: fixture.result.preparation_fingerprint };
        await createDeliveryActivationPreflight(body, "csrf", "key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation-delivery-preflights", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation-delivery-preflights/id%2Funsafe", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation-delivery-preflights", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "key" } });
    });
});
