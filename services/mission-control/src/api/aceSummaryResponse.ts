import type { AceSummary, IntelligenceTelemetry } from "../types/ace";

export class AceSummaryResponseError extends Error {
    constructor() {
        super("Advisory summary response could not be read.");
        this.name = "AceSummaryResponseError";
    }
}

type Row = Record<string, unknown>;
function object(value: unknown): Row {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new AceSummaryResponseError();
    return value as Row;
}
function string(value: unknown): string {
    if (typeof value !== "string") throw new AceSummaryResponseError();
    return value;
}
function nullableString(value: unknown): string | null {
    return value === null ? null : string(value);
}
function number(value: unknown, integer = false): number {
    if (typeof value !== "number" || !Number.isFinite(value) || (integer && !Number.isSafeInteger(value))) throw new AceSummaryResponseError();
    return value;
}
function nonnegative(value: unknown, integer = false): number {
    const result = number(value, integer);
    if (result < 0) throw new AceSummaryResponseError();
    return result;
}
function boolean(value: unknown): boolean {
    if (typeof value !== "boolean") throw new AceSummaryResponseError();
    return value;
}
function rows<T>(value: unknown, parse: (row: Row) => T): T[] {
    if (!Array.isArray(value)) throw new AceSummaryResponseError();
    return value.map(entry => parse(object(entry)));
}
function telemetry(value: unknown): IntelligenceTelemetry {
    const row = object(value);
    return {
        provider_collection_duration_ms: nonnegative(row.provider_collection_duration_ms),
        provider_timeout_seconds: nonnegative(row.provider_timeout_seconds),
        providers: rows(row.providers, timing => {
            if (timing.status !== "completed" && timing.status !== "timed_out" && timing.status !== "failed") throw new AceSummaryResponseError();
            return {
                provider_id: string(timing.provider_id), provider_name: string(timing.provider_name), status: timing.status,
                duration_ms: nonnegative(timing.duration_ms), finding_count: nonnegative(timing.finding_count, true),
            };
        }),
    };
}

// The endpoint emits a complete public AceSummary, including native defaults.
// Free-form metric/details dictionaries remain open; renderers check fields they use.
export function parseAceSummary(value: unknown): AceSummary {
    const row = object(value);
    return {
        score: number(row.score, true), status: string(row.status), summary: string(row.summary),
        findings: rows(row.findings, finding => ({
            id: string(finding.id), severity: string(finding.severity), category: string(finding.category),
            source: string(finding.source), title: string(finding.title), message: string(finding.message),
            recommendation: nullableString(finding.recommendation), component: nullableString(finding.component),
            metric: { ...object(finding.metric) }, details: { ...object(finding.details) },
            affects_health: boolean(finding.affects_health), score_penalty: number(finding.score_penalty, true),
        })),
        assessments: rows(row.assessments, assessment => ({
            title: string(assessment.title), priority: string(assessment.priority), component: nullableString(assessment.component),
            details: { ...object(assessment.details) },
        })),
        recommendations: rows(row.recommendations, recommendation => ({
            title: string(recommendation.title), reason: string(recommendation.reason), priority: string(recommendation.priority),
            confidence: number(recommendation.confidence), estimated_effort: string(recommendation.estimated_effort),
            component: nullableString(recommendation.component),
        })),
        telemetry: telemetry(row.telemetry),
    };
}
