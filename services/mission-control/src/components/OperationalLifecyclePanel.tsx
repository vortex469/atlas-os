import type { WorkflowOperationalLifecycle, WorkflowRecoveryDiagnostic } from "../types/atlasAgent";
import { operationalOutcome } from "../utils/operationalOutcome";

interface OperationalLifecyclePanelProps {
    lifecycle: WorkflowOperationalLifecycle | null;
    diagnostic?: WorkflowRecoveryDiagnostic | null;
    isLoading: boolean;
    isRefreshing: boolean;
    error: string | null;
    onRefresh: () => void;
}

function label(value: string | null): string {
    return value ? value.replaceAll("_", " ") : "Not reported";
}

function timestamp(value: string | null): string {
    if (!value) return "Not reported";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "Unknown time" : parsed.toLocaleString();
}

export function OperationalLifecyclePanel({ lifecycle, diagnostic, isLoading, isRefreshing, error, onRefresh }: OperationalLifecyclePanelProps) {
    if (isLoading) {
        return <section aria-label="Operational lifecycle"><p role="status" className="text-slate-300">Loading operational lifecycle...</p></section>;
    }
    if (error) {
        return <section aria-label="Operational lifecycle" role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5"><h2 className="text-lg font-semibold text-red-100">Operational lifecycle unavailable</h2><p className="mt-2 text-sm text-red-100">{error}</p><p className="mt-2 text-sm text-slate-300">A network failure is not an operational failure. No retry or provider action is available here.</p></section>;
    }
    if (!lifecycle || !lifecycle.applicable) return null;
    const outcome = operationalOutcome(lifecycle);
    return (
        <section aria-labelledby="operational-lifecycle-heading" className="space-y-5 rounded-xl border border-cyan-500/30 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="text-xs uppercase tracking-[0.2em] text-cyan-300">Operational workflow</p><h2 id="operational-lifecycle-heading" className="mt-2 text-xl font-semibold text-white">Operational lifecycle</h2></div>
                <button type="button" onClick={onRefresh} disabled={isRefreshing} className="rounded-lg border border-cyan-400/60 px-3 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50">{isRefreshing ? "Refreshing..." : "Refresh lifecycle"}</button>
            </div>
            <section aria-labelledby="outcome-heading" className="rounded-lg border border-slate-700 bg-slate-950/60 p-4">
                <h3 id="outcome-heading" className="font-semibold text-white">{outcome.title}</h3>
                <p className="mt-2 text-sm text-slate-300"><strong>Atlas knows:</strong> {outcome.known}</p>
                <p className="mt-1 text-sm text-slate-300"><strong>Atlas does not know:</strong> {outcome.unknown}</p>
                <p className="mt-1 text-sm text-cyan-200"><strong>Safe next step:</strong> {outcome.guidance}</p>
                {outcome.retryProhibited && <p className="mt-2 text-sm font-semibold text-amber-200">Mutation retry is prohibited. This view provides no retry or run-again control.</p>}
            </section>
            {diagnostic?.applicable && (
                <section aria-labelledby="recovery-diagnostic-heading" className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-4">
                    <h3 id="recovery-diagnostic-heading" className="font-semibold text-white">Recovery diagnostic</h3>
                    <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                        <div><dt className="text-slate-400">Status</dt><dd className="text-slate-100">{label(diagnostic.diagnostic_status)}</dd></div>
                        <div><dt className="text-slate-400">Consistency</dt><dd className="text-slate-100">{label(diagnostic.consistency)}</dd></div>
                        <div><dt className="text-slate-400">Controlled reason</dt><dd className="text-slate-100">{label(diagnostic.controlled_reason)}</dd></div>
                        <div><dt className="text-slate-400">Safe next action</dt><dd className="text-cyan-200">{label(diagnostic.safe_next_action)}</dd></div>
                    </dl>
                    <p className="mt-3 text-sm text-slate-300">Evidence: barrier {diagnostic.dispatch_evidence.barrier_crossed ? "crossed" : "not crossed"}; provider operation {diagnostic.dispatch_evidence.provider_operation_captured ? "captured" : "not captured"}; transition sequence {diagnostic.dispatch_evidence.transition_sequence_valid === true ? "valid" : diagnostic.dispatch_evidence.transition_sequence_valid === false ? "invalid" : "unavailable"}; target fingerprint {label(diagnostic.verification_evidence.target_fingerprint_state)}.</p>
                    <p className="mt-2 text-sm text-amber-200">This diagnostic is read-only and provides no retry, run-again, or reconciliation control.</p>
                </section>
            )}
            <LifecycleGroup title="Identity" values={[
                ["Workflow ID", lifecycle.workflow_id], ["Candidate ID", lifecycle.candidate_id], ["Planning Session ID", lifecycle.planning_session_id], ["Operation Intent", lifecycle.execution_intent], ["Provider / Resource", lifecycle.target_label],
            ]} />
            <LifecycleGroup title="Provenance" values={[
                ["Source Subsystem", lifecycle.candidate_source_subsystem], ["Operator Intent Record", lifecycle.operator_intent_record_id], ["Candidate Fingerprint", lifecycle.candidate_fingerprint], ["Plan Fingerprint", lifecycle.plan_fingerprint],
            ]} />
            <LifecycleGroup title="Approvals" values={[
                ["Preparation Approval", lifecycle.preparation_approval ? `${label(lifecycle.preparation_approval.presentation_state)} (${label(lifecycle.preparation_approval.decision_status)})` : null],
                ["Action Approval", lifecycle.action_approval ? `${label(lifecycle.action_approval.presentation_state)} (${label(lifecycle.action_approval.decision_status)})` : null],
                ["Action Approval Expiry", lifecycle.action_approval ? timestamp(lifecycle.action_approval.expires_at) : null],
            ]} />
            <LifecycleGroup title="Execution and exactly-once evidence" values={[
                ["Action Request ID", lifecycle.action_request_id], ["Disruption Scope", lifecycle.disruption_scope], ["Agent Execution Stage", label(lifecycle.agent_execution_stage)], ["Core Ledger State", label(lifecycle.core_record_state)], ["Dispatch Status", label(lifecycle.dispatch_status)],
                ["Barrier Crossed", lifecycle.barrier_crossed ? "Yes" : "No"], ["Barrier Crossing Count", String(lifecycle.barrier_crossing_count)], ["Provider Operation Captured", lifecycle.provider_operation_captured ? "Yes" : "No"], ["Provider Operation Capture Count", String(lifecycle.provider_operation_capture_count)],
            ]} />
            {lifecycle.terminal && lifecycle.barrier_crossing_count === 1 && lifecycle.provider_operation_capture_count <= 1 && <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">Exactly-once evidence shows one dispatch barrier crossing and no replay in the recorded lifecycle.</p>}
            <LifecycleGroup title="Verification" values={[
                ["Verification Status", label(lifecycle.verification_status)], ["Observed Service State", lifecycle.observed_state], ["Observed Health", lifecycle.observed_health], ["Provider Operation Reference", lifecycle.provider_operation_reference], ["Dispatch Started", timestamp(lifecycle.dispatch_started_at)], ["Dispatch Completed", timestamp(lifecycle.dispatch_completed_at)], ["Verification Started", timestamp(lifecycle.verification_started_at)], ["Verification Completed", timestamp(lifecycle.verification_completed_at)], ["Terminal", lifecycle.terminal ? "Yes" : "No"],
            ]} />
            <div><h3 className="font-semibold text-white">Durable transitions</h3>{lifecycle.transitions.length === 0 ? <p className="mt-2 text-sm text-slate-400">No Core transitions are available.</p> : <ol className="mt-3 space-y-2">{lifecycle.transitions.map((transition) => <li key={transition.sequence} className="text-sm text-slate-300"><span className="font-mono text-cyan-200">{transition.sequence}</span> · {label(transition.state)} · {timestamp(transition.occurred_at)}</li>)}</ol>}</div>
        </section>
    );
}

function LifecycleGroup({ title, values }: { title: string; values: Array<[string, string | null]> }) {
    return <section><h3 className="font-semibold text-white">{title}</h3><dl className="mt-3 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3">{values.map(([name, value]) => <div key={name}><dt className="text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-200">{value ?? "Not reported"}</dd></div>)}</dl></section>;
}
