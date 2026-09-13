import { Link } from "react-router-dom";
import { SectionHeader } from "../../components/SectionHeader";
import type { AceFinding, AceRecommendation } from "../../types/ace";

type OperatorAttentionProps = {
    findings?: AceFinding[];
    recommendations?: AceRecommendation[];
    blockedWorkflowCount?: number;
    degradedServiceCount?: number;
    unavailableProviderCount?: number;
};

/**
 * Operator attention and recent activity summary.
 * Surfaces actionable issues requiring operator awareness.
 * Prioritizes conditions over routine healthy noise.
 * Provides navigation to detail routes.
 * Deduplicates presentation across dashboard sections.
 */
export function OperatorAttentionSection({
    findings = [],
    recommendations = [],
    blockedWorkflowCount = 0,
    degradedServiceCount = 0,
    unavailableProviderCount = 0,
}: OperatorAttentionProps) {
    // Collect all actionable conditions
    const criticalFindings = findings.filter(
        (f) => f.severity === "critical" || f.affects_health,
    );
    const criticalRecommendations = recommendations.filter(
        (r) => r.priority === "critical" || r.priority === "high",
    );

    const hasIssues =
        blockedWorkflowCount > 0 ||
        degradedServiceCount > 0 ||
        unavailableProviderCount > 0 ||
        criticalFindings.length > 0 ||
        criticalRecommendations.length > 0;

    return (
        <section>
            <SectionHeader
                title="Operator Attention"
                description="Conditions requiring immediate operator awareness."
            />

            {!hasIssues ? (
                <div className="mc-surface rounded-mc-lg p-6">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">✅</span>
                        <div>
                            <p className="font-medium text-mc-text-primary">
                                No action required
                            </p>
                            <p className="text-sm text-mc-text-secondary">
                                All systems operating normally.
                            </p>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="space-y-4">
                    {/* Blocked workflows alert */}
                    {blockedWorkflowCount > 0 && (
                        <div className="rounded-mc-lg border border-mc-border-subtle bg-mc-surface p-4">
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1">
                                    <h3 className="font-medium text-mc-text-primary">
                                        ⚠️ {blockedWorkflowCount} Blocked Workflow
                                        {blockedWorkflowCount !== 1 ? "s" : ""}
                                    </h3>
                                    <p className="mt-1 text-sm text-mc-text-secondary">
                                        Workflows are blocked and waiting for
                                        approval or operator action.
                                    </p>
                                </div>
                                <Link
                                    to="/workflows?state=blocked"
                                    className="inline-flex whitespace-nowrap rounded-mc-sm border border-mc-border-subtle px-3 py-1 text-xs font-medium text-mc-primary transition hover:bg-mc-surface-elevated"
                                >
                                    Review
                                </Link>
                            </div>
                        </div>
                    )}

                    {/* Degraded services alert */}
                    {degradedServiceCount > 0 && (
                        <div className="rounded-mc-lg border border-mc-border-subtle bg-mc-surface p-4">
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1">
                                    <h3 className="font-medium text-mc-text-primary">
                                        ⚠️ {degradedServiceCount} Degraded Service
                                        {degradedServiceCount !== 1 ? "s" : ""}
                                    </h3>
                                    <p className="mt-1 text-sm text-mc-text-secondary">
                                        System services are responding slowly or
                                        have elevated error rates.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Unavailable providers alert */}
                    {unavailableProviderCount > 0 && (
                        <div className="rounded-mc-lg border border-mc-border-subtle bg-mc-surface p-4">
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1">
                                    <h3 className="font-medium text-mc-text-primary">
                                        🔌 {unavailableProviderCount} Unavailable
                                        Provider
                                        {unavailableProviderCount !== 1
                                            ? "s"
                                            : ""}
                                    </h3>
                                    <p className="mt-1 text-sm text-mc-text-secondary">
                                        External providers or integrations are not
                                        responding.
                                    </p>
                                </div>
                                <Link
                                    to="/providers"
                                    className="inline-flex whitespace-nowrap rounded-mc-sm border border-mc-border-subtle px-3 py-1 text-xs font-medium text-mc-primary transition hover:bg-mc-surface-elevated"
                                >
                                    Check
                                </Link>
                            </div>
                        </div>
                    )}

                    {/* Critical findings */}
                    {criticalFindings.length > 0 && (
                        <div className="rounded-mc-lg border border-mc-border-subtle bg-mc-surface p-4">
                            <h3 className="font-medium text-mc-text-primary">
                                🔍 {criticalFindings.length} Critical Finding
                                {criticalFindings.length !== 1 ? "s" : ""}
                            </h3>
                            <ul className="mt-3 space-y-2">
                                {criticalFindings.slice(0, 3).map((finding) => (
                                    <li
                                        key={finding.id}
                                        className="text-sm text-mc-text-secondary"
                                    >
                                        <span className="font-medium">
                                            {finding.title}
                                        </span>
                                        {finding.component && (
                                            <span className="ml-2 text-xs text-mc-text-muted">
                                                ({finding.component})
                                            </span>
                                        )}
                                    </li>
                                ))}
                            </ul>
                            {criticalFindings.length > 3 && (
                                <p className="mt-2 text-xs text-mc-text-muted">
                                    +{criticalFindings.length - 3} more findings
                                </p>
                            )}
                        </div>
                    )}

                    {/* Critical recommendations */}
                    {criticalRecommendations.length > 0 && (
                        <div className="rounded-mc-lg border border-mc-border-subtle bg-mc-surface p-4">
                            <h3 className="font-medium text-mc-text-primary">
                                💡 {criticalRecommendations.length} Recommended
                                Action
                                {criticalRecommendations.length !== 1 ? "s" : ""}
                            </h3>
                            <ul className="mt-3 space-y-2">
                                {criticalRecommendations.slice(0, 3).map((rec) => (
                                    <li
                                        key={rec.title}
                                        className="text-sm text-mc-text-secondary"
                                    >
                                        <span className="font-medium">
                                            {rec.title}
                                        </span>
                                        {rec.component && (
                                            <span className="ml-2 text-xs text-mc-text-muted">
                                                ({rec.component})
                                            </span>
                                        )}
                                    </li>
                                ))}
                            </ul>
                            {criticalRecommendations.length > 3 && (
                                <p className="mt-2 text-xs text-mc-text-muted">
                                    +{criticalRecommendations.length - 3} more
                                </p>
                            )}
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}
