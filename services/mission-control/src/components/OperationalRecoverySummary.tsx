import type { WorkflowRecoveryDiagnostic } from "../types/atlasAgent";
import { recoveryLabel, recoveryPresentation, type RecoverySeverity } from "../utils/recoveryDiagnostic";

interface OperationalRecoverySummaryProps {
    diagnostic: WorkflowRecoveryDiagnostic | null;
    isLoading?: boolean;
    error?: string | null;
    supportEvidenceAvailable: boolean;
    compact?: boolean;
}

const SEVERITY_STYLES: Record<RecoverySeverity, string> = {
    success: "border-emerald-500/40 bg-emerald-500/10",
    info: "border-cyan-500/40 bg-cyan-500/10",
    warning: "border-amber-500/40 bg-amber-500/10",
    danger: "border-red-500/40 bg-red-500/10",
    unavailable: "border-slate-600 bg-slate-800/60",
};

export function OperationalRecoverySummary({ diagnostic, isLoading = false, error = null, supportEvidenceAvailable, compact = false }: OperationalRecoverySummaryProps) {
    if (isLoading) return <section aria-label="Maintenance status summary"><p role="status" className="text-sm text-slate-300">Checking maintenance status…</p></section>;
    if (error) return <section aria-label="Maintenance status summary" className="rounded-lg border border-slate-600 bg-slate-800/60 p-4"><h3 className="font-semibold text-white">Maintenance status details unavailable</h3><p className="mt-2 text-sm text-slate-300">{error}</p><p className="mt-2 text-sm text-cyan-200">A problem checking status does not mean the maintenance request failed.</p></section>;
    if (!diagnostic?.applicable) return null;

    const presentation = recoveryPresentation(diagnostic);
    return <section aria-label="Maintenance status summary" className={`rounded-lg border p-4 ${SEVERITY_STYLES[presentation.severity]}`}>
        <h3 className="font-semibold text-white">{presentation.title}</h3>
        <p className="mt-2 text-sm text-slate-200">{presentation.reason}</p>
        {!compact && <details className="mt-3 rounded-lg border border-current/20 px-3 py-2">
            <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-200">Technical details</summary>
            <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                <Evidence label="Record consistency" value={recoveryLabel(diagnostic.consistency)} />
                <Evidence label="Target fingerprint" value={recoveryLabel(diagnostic.verification_evidence.target_fingerprint_state)} />
                <Evidence label="Dispatch barrier" value={diagnostic.dispatch_evidence.barrier_crossed ? "Crossed" : "Not crossed"} />
                <Evidence label="Provider operation" value={diagnostic.dispatch_evidence.provider_operation_captured ? "Captured" : "Not captured"} />
                <Evidence label="Verification" value={recoveryLabel(diagnostic.verification_evidence.status)} />
                <Evidence label="Observed state" value={diagnostic.verification_evidence.observed_state ?? "Not reported"} />
                <Evidence label="Observed health" value={diagnostic.verification_evidence.observed_health ?? "Not reported"} />
                <Evidence label="Transition sequence" value={diagnostic.dispatch_evidence.transition_sequence_valid === true ? "Valid" : diagnostic.dispatch_evidence.transition_sequence_valid === false ? "Mismatch" : "Unavailable"} />
                <Evidence label="Support evidence" value={supportEvidenceAvailable ? "Available" : "Unavailable"} />
            </dl>
        </details>}
        <p className="mt-3 text-sm font-medium text-cyan-100"><strong>Safe next action:</strong> {presentation.safeNextAction}</p>
        <p className="mt-2 text-xs text-slate-300">This page only reports status. It cannot change or repeat the request.</p>
    </section>;
}

function Evidence({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt><dd className="mt-1 text-slate-100">{value}</dd></div>;
}
