import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet, mockPost } = vi.hoisted(() => ({ mockGet: vi.fn(), mockPost: vi.fn() }));
vi.mock("axios", () => ({ default: {
    create: () => ({ get: mockGet, post: mockPost }),
    isAxiosError: (error: unknown) => !!error && typeof error === "object" && "isAxiosError" in error,
} }));
import { getAtlasDoctorReport, getAtlasErrorMessage } from "./atlas";
import { DoctorResponseError } from "./doctorResponse";

function report(patch: Record<string, unknown> = {}) {
    return { status: "healthy", score: 100, checked_at: "2026-10-26T12:00:00Z", configuration_ok: true,
        checks: [{ name: "Docker", passed: true, error: null }], critical: [], warnings: [], information: [], ...patch };
}
beforeEach(() => { mockGet.mockReset(); mockPost.mockReset(); });
afterEach(() => expect(mockPost).not.toHaveBeenCalled());

describe("Doctor read response", () => {
    it.each(["healthy", "degraded", "critical"])("reads a complete %s report without reclassifying it", async (status) => {
        const data = report({ status, score: 80 });
        mockGet.mockResolvedValueOnce({ data });
        await expect(getAtlasDoctorReport()).resolves.toEqual(data);
        expect(mockGet).toHaveBeenCalledExactlyOnceWith("/ops/doctor");
    });

    it("preserves Core's optional defaults and ignores additive response fields", async () => {
        mockGet.mockResolvedValueOnce({ data: { status: "healthy", score: 100, checked_at: "2026-10-26T12:00:00Z", configuration_ok: true, future_field: "ignored" } });
        await expect(getAtlasDoctorReport()).resolves.toEqual({ status: "healthy", score: 100, checked_at: "2026-10-26T12:00:00Z", configuration_ok: true, checks: [], critical: [], warnings: [], information: [] });
    });

    it("preserves a default-null check error without inventing a cause", async () => {
        mockGet.mockResolvedValueOnce({ data: report({ status: "critical", score: 80, checks: [{ name: "Docker", passed: false }] }) });
        await expect(getAtlasDoctorReport()).resolves.toMatchObject({ checks: [{ name: "Docker", passed: false, error: null }] });
    });

    it("leaves finding impact and score ownership with Core", async () => {
        const data = report({ warnings: ["A finding that does not affect Core health."], information: ["Native report note."] });
        mockGet.mockResolvedValueOnce({ data });
        await expect(getAtlasDoctorReport()).resolves.toMatchObject({ status: "healthy", score: 100, warnings: data.warnings });
    });

    it("accepts a well-formed future report for separate age handling", async () => {
        mockGet.mockResolvedValueOnce({ data: report({ checked_at: "2999-01-01T00:00:00Z" }) });
        await expect(getAtlasDoctorReport()).resolves.toMatchObject({ checked_at: "2999-01-01T00:00:00Z" });
    });

    it.each(["status", "score", "checked_at", "configuration_ok"])("rejects missing required fact %s", async (field) => {
        const data: Record<string, unknown> = report(); delete data[field];
        mockGet.mockResolvedValueOnce({ data });
        await expect(getAtlasDoctorReport()).rejects.toBeInstanceOf(DoctorResponseError);
    });

    it.each([
        ["status", "perfect"], ["score", "100"], ["score", -1], ["score", 101], ["score", 99.5], ["score", NaN], ["score", Infinity],
        ["checked_at", "2026-02-30T00:00:00Z"], ["checked_at", "2026-10-26T12:00:00"], ["configuration_ok", "true"],
        ["checks", null], ["checks", [null]], ["checks", [{ name: "Docker", passed: "true" }]], ["checks", [{ name: "", passed: true }]],
        ["checks", [{ name: "Docker", passed: true, error: {} }]], ["critical", null], ["warnings", {}], ["information", [42]],
    ])("rejects malformed %s=%j with a fixed owned message", async (field, value) => {
        mockGet.mockResolvedValueOnce({ data: report({ critical: ["private malformed report canary"], [field]: value }) });
        const error = await getAtlasDoctorReport().catch((error: unknown) => error);
        expect(error).toBeInstanceOf(DoctorResponseError);
        expect(getAtlasErrorMessage(error, "fallback")).toBe("The health-check report is incomplete or unreadable. Run Doctor to try again.");
        expect(getAtlasErrorMessage(error, "fallback")).not.toContain("private malformed report canary");
        expect(mockGet).toHaveBeenCalledTimes(1);
    });

    it.each([null, [], "unreadable"].map((data) => ({ data })))("rejects a non-object report %j", async ({ data }) => {
        mockGet.mockResolvedValueOnce({ data });
        await expect(getAtlasDoctorReport()).rejects.toBeInstanceOf(DoctorResponseError);
    });

    it("preserves transport failures and does not automatically retry", async () => {
        const error = { isAxiosError: true, response: { status: 503 } };
        mockGet.mockRejectedValueOnce(error);
        await expect(getAtlasDoctorReport()).rejects.toBe(error);
        expect(mockGet).toHaveBeenCalledTimes(1);
    });
});
