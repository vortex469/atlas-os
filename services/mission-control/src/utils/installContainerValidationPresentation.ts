const validationStatusLabels = {
    valid_but_unsupported: "Request valid; installation remains unsupported.",
    rejected: "Validation rejected this request.",
} as const;

const validationReasonLabels: Record<string, string> = {
    contract_malformed: "The validation request is malformed.",
    contract_unknown_field: "The request includes a field Atlas does not accept.",
    contract_out_of_bounds: "The request exceeds the allowed limits.",
    request_fingerprint_mismatch: "The request contents do not match their fingerprint.",
    request_not_current: "The request is no longer current.",
    request_replay_or_duplicate: "This request was already used or duplicated.",
    candidate_proof_missing: "The proposal proof is missing.",
    candidate_proof_mismatch: "The proposal proof does not match the current proposal.",
    candidate_not_active: "The proposal is no longer active.",
    approval_proof_missing: "The required approval proof is missing.",
    approval_proof_mismatch: "The approval proof does not match the request.",
    subject_unsupported: "This target is not supported.",
    destination_identity_mismatch: "The destination identity does not match the reviewed target.",
    artifact_unsupported: "This deployment artifact type is not supported.",
    artifact_source_mismatch: "The deployment artifact does not match its reviewed source.",
    image_not_digest_pinned: "The container image is not pinned to a fixed digest.",
    runtime_boundary_violated: "The requested runtime settings exceed the allowed limits.",
    filesystem_boundary_violated: "The requested file access exceeds the allowed limits.",
    network_boundary_violated: "The requested network access exceeds the allowed limits.",
    validation_dependency_unavailable: "A required validation dependency is unavailable.",
    validation_contract_failure: "The validation contract could not verify the request.",
};

function humanizeUnknownCode(value: string): string {
    const words = value.trim().replaceAll(/[_-]+/g, " ").replace(/\s+/g, " ");
    return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Unknown validation reason";
}

export function formatInstallContainerValidationStatus(
    status: keyof typeof validationStatusLabels,
): string {
    return validationStatusLabels[status];
}

export function formatInstallContainerValidationReason(reasonCode: string): string {
    const normalized = reasonCode.trim().toLowerCase();
    return Object.hasOwn(validationReasonLabels, normalized)
        ? validationReasonLabels[normalized]
        : humanizeUnknownCode(reasonCode);
}
