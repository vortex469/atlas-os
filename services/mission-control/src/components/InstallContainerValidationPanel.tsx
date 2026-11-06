import type {
    InstallContainerCapability,
    InstallContainerRedactedError,
    InstallContainerValidation,
} from "../types/atlasAgent";
import { formatInstallContainerValidationReason, formatInstallContainerValidationStatus } from "../utils/installContainerValidationPresentation";
import { formatResourceReference, formatResourceTargetLabel } from "../utils/resourceLabels";

interface Props {
    capability: InstallContainerCapability;
    validation: InstallContainerValidation | null;
    error: InstallContainerRedactedError | null;
}

function Fingerprint({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <dt className="text-slate-500">{label}</dt>
            <dd className="break-all font-mono text-xs text-slate-300">sha256:{value}</dd>
        </div>
    );
}

const authorityNotice = "Validation is not installation, execution approval, dispatch, deployment, rollback, or permission to mutate anything.";

export function InstallContainerValidationPanel({ capability, validation, error }: Props) {
    return (
        <section aria-labelledby="install-container-validation-title" className="mt-5 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h3 id="install-container-validation-title" className="font-semibold text-slate-100">Agent install-container validation</h3>
                    <p className="mt-1 text-sm font-medium text-amber-200">{authorityNotice}</p>
                </div>
                <span className="rounded-full border border-amber-400/40 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-amber-200">
                    Unsupported · default-disabled
                </span>
            </div>

            <dl className="mt-4 grid gap-3 text-sm md:grid-cols-3">
                <div><dt className="text-slate-500">Runtime bounds</dt><dd className="text-slate-300">{capability.runtime}</dd></div>
                <div><dt className="text-slate-500">Filesystem bounds</dt><dd className="text-slate-300">{capability.filesystem}</dd></div>
                <div><dt className="text-slate-500">Network bounds</dt><dd className="text-slate-300">{capability.network}</dd></div>
            </dl>

            <p className="mt-4 text-sm text-slate-300">
                Home Assistant remains blocked: its deployment artifact and proof chain are absent, and its persistent/networked requirements are outside this contract.
            </p>

            {error && (
                <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                    <p className="font-semibold">Validation diagnostic unavailable (redacted)</p>
                    <p>{formatInstallContainerValidationReason(error.reason_code)}</p>
                    <p>No request content, credentials, provider payload, paths, or exception details are shown.</p>
                    <details className="mt-2"><summary className="cursor-pointer text-sm font-medium text-slate-300">Technical details</summary><p className="mt-1">Reason code: {error.reason_code}</p><p>Correlation ID: {error.correlation_id}</p></details>
                </div>
            )}

            {!error && !validation && (
                <p className="mt-4 text-sm text-slate-500">No validation result is locally available. Atlas exposes no Core request route or Core-to-Agent bridge for this contract.</p>
            )}

            {!error && validation && (
                <div className="mt-4 space-y-4 border-t border-slate-800 pt-4 text-sm">
                    <section aria-label="Validation result" className="space-y-2">
                        <p className="font-semibold text-slate-200">{formatInstallContainerValidationStatus(validation.status)}</p>
                        <p className="text-slate-400">Validated at {validation.validated_at}</p>
                        <p className="text-slate-300">Validated target: {formatResourceTargetLabel(validation.evidence.subject.provider, validation.evidence.subject.resource_type, validation.evidence.subject.resource_id)}</p>
                        {validation.reason_codes.length > 0 && <ul aria-label="Validation reasons" className="list-disc space-y-1 pl-5 text-red-300">{validation.reason_codes.map((reason) => <li key={reason}>{formatInstallContainerValidationReason(reason)}</li>)}</ul>}
                    </section>

                    <details className="rounded border border-slate-700 px-3 py-2">
                        <summary className="cursor-pointer font-medium text-slate-300">Technical evidence</summary>
                        <div className="mt-3 space-y-4">
                            <dl className="grid gap-3 md:grid-cols-2">
                                <Fingerprint label="Request proof fingerprint" value={validation.request_fingerprint.value} />
                                <Fingerprint label="Validation fingerprint" value={validation.validation_fingerprint.value} />
                                <Fingerprint label="Audit evidence fingerprint" value={validation.evidence.evidence_fingerprint.value} />
                                <Fingerprint label="Runtime/limit policy fingerprint" value={validation.evidence.runtime_limit_policy_fingerprint.value} />
                                <Fingerprint label="Candidate envelope fingerprint" value={validation.evidence.approval.candidate_envelope_fingerprint.value} />
                                <Fingerprint label="Approval intent fingerprint" value={validation.evidence.approval.approval_intent_fingerprint.value} />
                            </dl>

                            <div>
                                <h4 className="font-semibold text-slate-200">Artifact reference</h4>
                                <p className="break-all text-slate-300">{validation.evidence.source_repository_path} · {validation.evidence.source_service}</p>
                                <p className="break-all font-mono text-xs text-slate-400">{validation.evidence.source_content_digest} · {validation.evidence.image_digest}</p>
                            </div>

                            <div>
                                <h4 className="font-semibold text-slate-200">Audit evidence</h4>
                                <p className="text-slate-400">Request {validation.evidence.request_id}; candidate {validation.evidence.approval.candidate_record_id}; approval {validation.evidence.approval.approval_intent_id}</p>
                                <p className="text-slate-400">Subject reference: {formatResourceReference(validation.evidence.subject.provider, validation.evidence.subject.resource_type, validation.evidence.subject.resource_id)}</p>
                                <p className="text-slate-400">Status code: {validation.status}</p>
                                {validation.reason_codes.length > 0 && <p className="text-slate-400">Reason codes: {validation.reason_codes.join(", ")}</p>}
                                <p className="mt-2 text-amber-200">Execution supported: no · Dispatch allowed: no · Mutation allowed: no · Replay allowed: no</p>
                            </div>
                        </div>
                    </details>
                </div>
            )}
        </section>
    );
}
