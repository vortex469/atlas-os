import { beforeEach, describe, expect, it, vi } from "vitest";
const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("axios", () => ({ default: { create: () => ({ post }), isAxiosError: () => false } }));
import { runProviderAction } from "./atlas";
import { ProviderActionResponseError } from "./providerActionResponse";

function response(patch: Record<string, unknown> = {}): Record<string, unknown> {
    return { provider_id: "fixture", action_id: "run-diagnostics", status: "succeeded", success: true,
        message: "Synthetic result.", data: {}, warnings: [], ...patch };
}
beforeEach(() => post.mockReset());
describe("Provider action response binding", () => {
    it.each([true, false])("returns only a matching reported result, success=%s", async (success) => {
        const data = response({ success, status: success ? "succeeded" : "failed" });
        post.mockResolvedValueOnce({ data });
        await expect(runProviderAction("fixture", "run-diagnostics", { confirmed: true, parameters: { model: "synthetic" } })).resolves.toEqual(data);
        expect(post).toHaveBeenCalledExactlyOnceWith("/providers/fixture/actions/run-diagnostics", { confirmed: true, parameters: { model: "synthetic" } });
    });
    it("preserves the native optional result defaults and request defaults", async () => {
        const data = response(); delete data.data; delete data.warnings;
        post.mockResolvedValueOnce({ data: { ...data, future_field: true } });
        await expect(runProviderAction("fixture", "run-diagnostics")).resolves.toEqual(response());
        expect(post).toHaveBeenCalledExactlyOnceWith("/providers/fixture/actions/run-diagnostics", { confirmed: false, parameters: {} });
    });
    it.each([
        { provider_id: "foreign" }, { action_id: "foreign" }, { status: "pending" }, { success: false }, { success: "true" },
        { message: null }, { data: [] }, { data: null }, { warnings: null }, { warnings: [{}] },
    ])("treats an unbound or malformed response as unconfirmed: %j", async (patch) => {
        post.mockResolvedValueOnce({ data: response(patch) });
        await expect(runProviderAction("fixture", "run-diagnostics")).rejects.toBeInstanceOf(ProviderActionResponseError);
        expect(post).toHaveBeenCalledTimes(1);
    });
    it.each(["provider_id", "action_id", "status", "success", "message"])("requires outcome fact %s", async (field) => {
        const data = response(); delete data[field];
        post.mockResolvedValueOnce({ data });
        await expect(runProviderAction("fixture", "run-diagnostics")).rejects.toBeInstanceOf(ProviderActionResponseError);
    });
    it("does not retry a transport failure", async () => {
        const error = new Error("synthetic lost response"); post.mockRejectedValueOnce(error);
        await expect(runProviderAction("fixture", "run-diagnostics")).rejects.toBe(error);
        expect(post).toHaveBeenCalledTimes(1);
    });
});
