import { describe, expect, it } from "vitest";

import { compatibilityStatusLabel, executionConstraintLabel } from "./operatorLanguage";

describe("operator language labels", () => {
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
