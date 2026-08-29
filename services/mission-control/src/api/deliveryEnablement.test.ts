import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { createDeliveryEnablement, getDeliveryEnablement, listDeliveryEnablements, parseDeliveryEnablement, parseDeliveryEnablementError } from "./deliveryEnablement";
import { deliveryEnablementFixture as fixture } from "../test/deliveryEnablement";
import { DELIVERY_ENABLEMENT_CONFIRMATION } from "../types/deliveryEnablement";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

describe("delivery enablement API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded create/list/get with credentials", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { enablements: [fixture], next_cursor: null } }).mockResolvedValueOnce({ data: fixture });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: fixture });
        const create = { schema: "operator-controlled-delivery-enablement-create-v1" as const, preflight_id: fixture.record.preflight_id, preflight_fingerprint: fixture.record.preflight_fingerprint, confirmation: DELIVERY_ENABLEMENT_CONFIRMATION };
        expect((await listDeliveryEnablements()).enablements).toEqual([fixture]);
        await getDeliveryEnablement("id/unsafe"); await createDeliveryEnablement(create, "csrf", "stable-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation-delivery-enablements", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation-delivery-enablements/id%2Funsafe", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation-delivery-enablements", create, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "stable-key" } });
    });

    it("strictly rejects unknown, mismatched, stale, authority, and confirmation data", () => {
        expect(parseDeliveryEnablement(fixture)).toEqual(fixture);
        expect(() => parseDeliveryEnablement({ ...fixture, raw_log: "secret" })).toThrow(/invalid/i);
        expect(() => parseDeliveryEnablement({ ...fixture, delivery_sent: true })).toThrow(/invalid/i);
        expect(() => parseDeliveryEnablement({ ...fixture, record: { ...fixture.record, confirmation: "yes" } })).toThrow(/invalid/i);
        expect(() => parseDeliveryEnablement({ ...fixture, record: { ...fixture.record, expires_at: "2026-08-29T12:00:32Z" } })).toThrow(/invalid/i);
        expect(() => parseDeliveryEnablement({ ...fixture, status: { ...fixture.status, enablement_id: "00000000-0000-4000-8000-000000000999" } })).toThrow(/invalid/i);
        expect(() => parseDeliveryEnablement({ ...fixture, record: { ...fixture.record, linkage: { ...fixture.record.linkage, preflight_fingerprint: { ...fixture.record.linkage.preflight_fingerprint, value: "1".repeat(64) } } } })).toThrow(/invalid/i);
    });

    it("accepts only the closed redacted error shape", () => {
        const error = { schema: "operator-controlled-delivery-enablement-error-v1", error_code: "unavailable", correlation_id: "enablement-redacted", preflight_id: null, preflight_fingerprint: null, redacted: true };
        expect(parseDeliveryEnablementError(error).redacted).toBe(true);
        expect(() => parseDeliveryEnablementError({ ...error, detail: "/internal/path" })).toThrow(/invalid/i);
        expect(() => parseDeliveryEnablementError({ ...error, redacted: false })).toThrow(/invalid/i);
    });
});
