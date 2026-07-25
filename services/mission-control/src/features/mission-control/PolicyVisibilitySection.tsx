import { SectionHeader } from "../../components/SectionHeader";
import type {
    AtlasPolicies,
    PolicySeverity,
} from "../../types/policies";

type PolicyVisibilitySectionProps = {
    policies: AtlasPolicies;
};

type PolicyRow = {
    provider: string;
    expectation: string;
    scope: string;
    severity: PolicySeverity;
};

const severityStyles: Record<PolicySeverity, string> = {
    critical: "text-red-300",
    warning: "text-amber-300",
    info: "text-blue-300",
};

function formatSeverity(severity: PolicySeverity): string {
    return (
        severity.charAt(0).toUpperCase() + severity.slice(1)
    );
}

export function PolicyVisibilitySection({
    policies,
}: PolicyVisibilitySectionProps) {
    const rows: PolicyRow[] = [
        {
            provider: "OPNsense",
            expectation:
                policies.opnsense.pending_update_warning_threshold ===
                null
                    ? "Updates remain informational"
                    : `Warn at ${policies.opnsense.pending_update_warning_threshold} pending update(s)`,
            scope: "Pending updates",
            severity:
                policies.opnsense.pending_update_warning_threshold ===
                null
                    ? "info"
                    : "warning",
        },
        {
            provider: "OPNsense",
            expectation: "Reboot required",
            scope: "Firmware maintenance",
            severity: policies.opnsense.reboot_required_severity,
        },
        {
            provider: "Frigate",
            expectation: `${Object.keys(policies.frigate.cameras).length} camera expectation(s)`,
            scope: "Camera health",
            severity: policies.frigate.stalled_camera_severity,
        },
        {
            provider: "Obsidian",
            expectation: `At least ${policies.obsidian.minimum_note_count} note(s)`,
            scope:
                policies.obsidian.stale_after_days === null
                    ? "Freshness disabled"
                    : `${policies.obsidian.stale_after_days}-day freshness`,
            severity:
                policies.obsidian.insufficient_notes_severity,
        },
        {
            provider: "Obsidian",
            expectation:
                policies.obsidian.stale_after_days === null
                    ? "Freshness disabled"
                    : `${policies.obsidian.stale_after_days}-day freshness`,
            scope: "Stale vault",
            severity: policies.obsidian.stale_severity,
        },
        {
            provider: "Obsidian",
            expectation: "Metadata scan file cap",
            scope: "Truncated scan",
            severity: policies.obsidian.scan_truncated_severity,
        },
        {
            provider: "Qdrant",
            expectation: `${policies.qdrant.expected_collections.length} expected collection(s)`,
            scope: "Missing collections",
            severity: policies.qdrant.missing_collection_severity,
        },
        {
            provider: "Qdrant",
            expectation: "No collections present",
            scope: "Empty instance",
            severity: policies.qdrant.empty_instance_severity,
        },
        {
            provider: "n8n",
            expectation: `${policies.n8n.expected_active_workflows.length} expected active workflow(s)`,
            scope: "Inactive workflows",
            severity: policies.n8n.inactive_workflow_severity,
        },
        {
            provider: "n8n",
            expectation: "Workflow inventory cap",
            scope: "Truncated scan",
            severity: policies.n8n.scan_truncated_severity,
        },
        {
            provider: "n8n",
            expectation: "No workflows present",
            scope: "Empty instance",
            severity: policies.n8n.empty_instance_severity,
        },
    ];

    return (
        <section>
            <SectionHeader
                title="Provider Policies"
                description="Live validated operational expectations currently enforced by ACE."
            />

            <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900">
                <table className="w-full min-w-[620px] text-left text-sm">
                    <thead className="border-b border-slate-800 bg-slate-950/40 text-xs uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                            <th className="px-5 py-3 font-medium">
                                Provider
                            </th>
                            <th className="px-5 py-3 font-medium">
                                Expectation
                            </th>
                            <th className="px-5 py-3 font-medium">
                                Finding scope
                            </th>
                            <th className="px-5 py-3 font-medium">
                                Severity
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                        {rows.map((row) => (
                            <tr key={row.provider}>
                                <td className="px-5 py-4 font-medium text-slate-200">
                                    {row.provider}
                                </td>
                                <td className="px-5 py-4 text-slate-300">
                                    {row.expectation}
                                </td>
                                <td className="px-5 py-4 text-slate-400">
                                    {row.scope}
                                </td>
                                <td
                                    className={`px-5 py-4 font-semibold ${severityStyles[row.severity]}`}
                                >
                                    {formatSeverity(row.severity)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
