import { describe, expect, it } from "vitest";

import { compatibilityStatusLabel, executionCandidateStatusLabel, executionConstraintLabel } from "./operatorLanguage";

describe("operator language labels", () => {
    it.each([
        ["eligible", null, "Eligible for planning"],
        ["not_eligible", null, "Not eligible for planning"],
        ["eligible", "2000-01-01T00:00:00Z", "Expired"],
        ["not_eligible", "2000-01-01T00:00:00Z", "Expired"],
        ["eligible", "invalid", "Eligibility unavailable"],
        ["expired", null, "Expired"],
        ["future_state", null, "Eligibility unavailable"],
    ])("describes proposal eligibility %s without presenting unknown or expired status as eligible", (status, expiresAt, expected) => {
        expect(executionCandidateStatusLabel(status, expiresAt, Date.parse("2026-01-01T00:00:00Z"))).toBe(expected);
    });

    it.each([
        ["compatible", "Compatible"],
        ["compatible_with_warnings", "Compatible with warnings"],
        ["insufficient_information", "Not enough information"],
        ["incompatible", "Not compatible"],
        ["future_status", "Future status"],
        ["constructor", "Constructor"],
    ])("uses clear wording for compatibility status %s", (status, expected) => {
        expect(compatibilityStatusLabel(status)).toBe(expected);
    });

    it.each([
        ["requires-backup", "Backup required"],
        ["requires-provider", "Provider connection required"],
        ["requires-connectivity", "Network access required"],
        ["requires-compatibility", "Compatibility check required"],
        ["requires-resolved-relationships", "Related resources must be confirmed"],
        ["requires-current-evidence", "Current evidence required"],
        ["manual-step-required", "Manual step required"],
        ["destructive-change", "Destructive change"],
        ["service-disruption", "May interrupt service"],
        ["service_disruption", "May interrupt service"],
        ["future_constraint", "Future constraint"],
        ["constructor", "Constructor"],
    ])("uses clear wording for proposal constraint %s", (constraint, expected) => {
        expect(executionConstraintLabel(constraint)).toBe(expected);
    });
});
