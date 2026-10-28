const compatibilityLabels: Record<string, string> = {
    compatible: "Compatible",
    compatible_with_warnings: "Compatible with warnings",
    insufficient_information: "Not enough information",
    incompatible: "Not compatible",
};

const executionConstraintLabels: Record<string, string> = {
    "requires-backup": "Backup required",
    "requires-provider": "Provider connection required",
    "requires-connectivity": "Network access required",
    "requires-compatibility": "Compatibility check required",
    "requires-resolved-relationships": "Related resources must be confirmed",
    "requires-current-evidence": "Current evidence required",
    "manual-step-required": "Manual step required",
    "destructive-change": "Destructive change",
    "service-disruption": "May interrupt service",
};

function humanizeCode(value: string): string {
    const words = value.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ").toLowerCase();
    return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Unknown";
}

export function compatibilityStatusLabel(status: string): string {
    const normalized = status.trim().toLowerCase();
    return Object.hasOwn(compatibilityLabels, normalized)
        ? compatibilityLabels[normalized]
        : humanizeCode(status);
}

export function executionConstraintLabel(constraint: string): string {
    const normalized = constraint.trim().toLowerCase().replaceAll("_", "-");
    return Object.hasOwn(executionConstraintLabels, normalized)
        ? executionConstraintLabels[normalized]
        : humanizeCode(constraint);
}
