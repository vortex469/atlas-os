import { describe, expect, it } from "vitest";

import {
    formatInstallContainerValidationReason,
    formatInstallContainerValidationStatus,
} from "./installContainerValidationPresentation";

describe("install-container validation presentation", () => {
    it("explains validation outcomes without implying installation is enabled", () => {
        expect(formatInstallContainerValidationStatus("valid_but_unsupported"))
            .toBe("Request valid; installation remains unsupported.");
        expect(formatInstallContainerValidationStatus("rejected"))
            .toBe("Validation rejected this request.");
    });

    it.each([
        ["network_boundary_violated", "The requested network access exceeds the allowed limits."],
        ["candidate_proof_missing", "The proposal proof is missing."],
        ["validation_dependency_unavailable", "A required validation dependency is unavailable."],
        ["future_reason_code", "Future reason code"],
        ["", "Unknown validation reason"],
    ])("presents %s as readable operator text", (code, label) => {
        expect(formatInstallContainerValidationReason(code)).toBe(label);
    });
});
