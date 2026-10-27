import { describe, expect, it } from "vitest";
import fixture from "../test/aceSummary.fixture.json";
import { parseAceSummary, AceSummaryResponseError } from "./aceSummaryResponse";

const populated = fixture[1];
const finding = populated.findings[0];
const recommendation = populated.recommendations[0];

describe("advisory summary response", () => {
    it.each(fixture.map((value, index) => ({ value, index })))("reads native public model $index without inventing stricter enums or ranges", ({ value }) => {
        expect(parseAceSummary(value)).toEqual(value);
    });
    it("projects known public fields and preserves open details dictionaries", () => {
        const input = { ...populated, private: "PRIVATE-SUMMARY-CANARY", findings: [{ ...finding, private: "PRIVATE-SUMMARY-CANARY" }] };
        const result = parseAceSummary(input);
        expect(JSON.stringify(result)).not.toContain("PRIVATE-SUMMARY-CANARY");
        expect(result.findings[0].details).toEqual(finding.details);
        expect(result.findings[0].details).not.toBe(finding.details);
        expect(result.findings[0].severity).toBe("future_severity");
    });
    it.each([
        { name: "null", value: null }, { name: "array", value: [] },
        { name: "missing summary", value: { ...populated, summary: undefined } },
        { name: "invalid summary text", value: { ...populated, summary: {} } },
        { name: "fractional score", value: { ...populated, score: 1.5 } },
        { name: "unsafe score", value: { ...populated, score: Number.MAX_SAFE_INTEGER + 1 } },
        { name: "missing findings", value: { ...populated, findings: undefined } },
        { name: "null findings", value: { ...populated, findings: null } },
        { name: "null finding", value: { ...populated, findings: [null] } },
        ...["id", "severity", "category", "source", "title", "message", "recommendation", "component"].map(field => ({ name: `invalid finding ${field}`, value: { ...populated, findings: [{ ...finding, [field]: {} }] } })),
        { name: "invalid boolean", value: { ...populated, findings: [{ ...finding, affects_health: "false" }] } },
        { name: "unsafe penalty", value: { ...populated, findings: [{ ...finding, score_penalty: Infinity }] } },
        { name: "null details", value: { ...populated, findings: [{ ...finding, details: null }] } },
        { name: "array metric", value: { ...populated, findings: [{ ...finding, metric: [] }] } },
        { name: "invalid assessments", value: { ...populated, assessments: [{ title: "Review", priority: null, component: null, details: {} }] } },
        { name: "invalid recommendations", value: { ...populated, recommendations: null } },
        ...["title", "reason", "priority", "estimated_effort", "component"].map(field => ({ name: `invalid recommendation ${field}`, value: { ...populated, recommendations: [{ ...recommendation, [field]: {} }] } })),
        { name: "invalid confidence", value: { ...populated, recommendations: [{ ...recommendation, confidence: NaN }] } },
        { name: "missing telemetry", value: { ...populated, telemetry: undefined } },
        { name: "invalid duration", value: { ...populated, telemetry: { ...populated.telemetry, provider_collection_duration_ms: -1 } } },
        { name: "nonfinite timeout", value: { ...populated, telemetry: { ...populated.telemetry, provider_timeout_seconds: Infinity } } },
        { name: "invalid timings", value: { ...populated, telemetry: { ...populated.telemetry, providers: {} } } },
        ...[{ status: "unknown" }, { duration_ms: null }, { finding_count: -1 }, { finding_count: Number.MAX_SAFE_INTEGER + 1 }].map(fields => ({ name: `invalid timing ${JSON.stringify(fields)}`, value: { ...populated, telemetry: { ...populated.telemetry, providers: [{ ...populated.telemetry.providers[0], ...fields }] } } })),
    ])("rejects $name with a controlled message", ({ value }) => {
        expect(() => parseAceSummary(value)).toThrow(AceSummaryResponseError);
        expect(() => parseAceSummary(value)).toThrow("Advisory summary response could not be read.");
    });
});
