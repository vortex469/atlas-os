import { describe, expect, it } from "vitest";
import fixture from "../test/intelligenceHistory.fixture.json";
import { IntelligenceHistoryResponseError, parseIntelligenceHistory } from "./intelligenceHistoryResponse";

const row = fixture[0];
const timing = row.telemetry.providers[0];
const withTiming = (value: unknown) => [{ ...row, telemetry: { ...row.telemetry, providers: [value] } }];

describe("collection history responses", () => {
    it("accepts native public examples and datetime/default shapes", () => {
        expect(parseIntelligenceHistory(fixture)).toEqual(fixture);
        expect(parseIntelligenceHistory([{ ...fixture[3], telemetry: {} }])).toEqual([fixture[3]]);
        expect(parseIntelligenceHistory([])).toEqual([]);
    });

    it("projects known fields without mutating or reordering the response", () => {
        const value = [{ ...row, private_detail: "private-fixture-canary", telemetry: { ...row.telemetry, extra: true } }];
        expect(parseIntelligenceHistory(value)).toEqual([row]);
        expect(value[0].private_detail).toBe("private-fixture-canary");
    });

    it.each([
        { name: "null", value: null }, { name: "object", value: { items: [] } },
        { name: "null row", value: [null] }, { name: "missing id", value: [{ ...row, id: undefined }] },
        { name: "duplicate id", value: [row, row] }, { name: "missing time", value: [{ ...row, collected_at: undefined }] },
        { name: "impossible time", value: [{ ...row, collected_at: "2026-02-30T12:00:00Z" }] },
        { name: "invalid year zero", value: [{ ...row, collected_at: "0000-01-01T12:00:00Z" }] },
        { name: "invalid time", value: [{ ...row, collected_at: "private-fixture-canary" }] },
        { name: "null telemetry", value: [{ ...row, telemetry: null }] },
        { name: "null providers", value: [{ ...row, telemetry: { providers: null } }] },
        { name: "bad total duration", value: [{ ...row, telemetry: { ...row.telemetry, provider_collection_duration_ms: "12" } }] },
        { name: "negative timeout", value: [{ ...row, telemetry: { ...row.telemetry, provider_timeout_seconds: -1 } }] },
        { name: "missing provider", value: withTiming({ ...timing, provider_id: undefined }) },
        { name: "missing name", value: withTiming({ ...timing, provider_name: undefined }) },
        { name: "bad status", value: withTiming({ ...timing, status: "healthy" }) },
        { name: "null duration", value: withTiming({ ...timing, duration_ms: null }) },
        { name: "negative duration", value: withTiming({ ...timing, duration_ms: -1 }) },
        { name: "nonfinite duration", value: withTiming({ ...timing, duration_ms: Infinity }) },
        { name: "NaN duration", value: withTiming({ ...timing, duration_ms: NaN }) },
        { name: "fractional count", value: withTiming({ ...timing, finding_count: 1.2 }) },
        { name: "unsafe count", value: withTiming({ ...timing, finding_count: Number.MAX_SAFE_INTEGER + 1 }) },
        { name: "negative count", value: withTiming({ ...timing, finding_count: -1 }) },
    ])("rejects $name with an owned error", ({ value }) => {
        expect(() => parseIntelligenceHistory(value)).toThrow(IntelligenceHistoryResponseError);
        expect(() => parseIntelligenceHistory(value)).toThrow("Collection history response could not be read.");
    });
});
