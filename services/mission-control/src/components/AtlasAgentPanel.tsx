import { useAtlasAgent } from "../hooks/useAtlasAgent";
import { ApprovalCard } from "./ApprovalCard";
import { InstallContainerValidationPanel } from "./InstallContainerValidationPanel";

interface StatusCardProps {
    title: string;
    children: React.ReactNode;
}

function StatusCard({ title, children }: StatusCardProps) {
    return (
        <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h3 className="text-sm font-semibold text-slate-200">
                {title}
            </h3>
            <div className="mt-3 space-y-2 text-sm text-slate-400">
                {children}
            </div>
        </div>
    );
}

function UnpublishedStatus() {
    return (
        <p className="text-slate-500">Not published yet</p>
    );
}

export function AtlasAgentPanel() {
    const {
        info,
        repository,
        sprint,
        verification,
        review,
        approvals,
        isLoading,
        error,
        retry,
    } = useAtlasAgent();

    const pendingApprovals = approvals.filter(
        (approval) => approval.status === "pending",
    );

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div>
                <h2 className="font-semibold text-slate-100">
                    Atlas Agent
                </h2>
                <p className="mt-1 text-sm text-slate-400">
                    Read-only repository and workflow status from the
                    Atlas Agent service.
                </p>
            </div>

            {isLoading && (
                <p className="mt-5 text-sm text-slate-500">
                    Loading Atlas Agent status...
                </p>
            )}

            {error && (
                <div
                    role="alert"
                    className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
                >
                    <p className="font-semibold text-red-300">
                        Atlas Agent unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">
                        Mission Control could not load repository and workflow status. Try again to check the latest information.
                    </p>
                    <button type="button" onClick={retry} disabled={isLoading} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 text-sm font-semibold text-red-100 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:opacity-50">
                        Retry status
                    </button>
                </div>
            )}

            {!isLoading && !error && repository && (
                <>
                    <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <StatusCard title="Repository">
                        <p className="break-all text-slate-300">
                            {repository.root}
                        </p>
                        <p>
                            Branch:{" "}
                            <span className="text-slate-300">
                                {repository.branch ?? "Detached"}
                            </span>
                        </p>
                        <p>
                            Commit:{" "}
                            <span className="text-slate-300">
                                {repository.head_commit ?? "Not reported"}
                            </span>
                        </p>
                        <p
                            className={
                                repository.is_clean
                                    ? "text-emerald-300"
                                    : "text-amber-300"
                            }
                        >
                            {repository.is_clean
                                ? "Working tree clean"
                                : "Working tree has changes"}
                        </p>
                    </StatusCard>

                    <StatusCard title="Sprint">
                        {sprint ? (
                            <>
                                <p className="font-medium text-slate-300">
                                    {sprint.checkpoint_id}:{" "}
                                    {sprint.title}
                                </p>
                                <p>{sprint.goal}</p>
                                <p>
                                    Phase:{" "}
                                    <span className="text-slate-300">
                                        {sprint.phase}
                                    </span>
                                </p>
                            </>
                        ) : (
                            <UnpublishedStatus />
                        )}
                    </StatusCard>

                    <StatusCard title="Verification">
                        {verification ? (
                            <>
                                <p className="text-slate-300">
                                    Status: {verification.status}
                                </p>
                                <p>
                                    Checks:{" "}
                                    {verification.results.length}
                                </p>
                                <p>
                                    Duration:{" "}
                                    {verification.duration_seconds.toFixed(
                                        2,
                                    )}
                                    s
                                </p>
                            </>
                        ) : (
                            <UnpublishedStatus />
                        )}
                    </StatusCard>

                    <StatusCard title="Review">
                        {review ? (
                            <>
                                <p className="text-slate-300">
                                    Status: {review.status}
                                </p>
                                <p>
                                    Findings: {review.findings.length}
                                </p>
                                <p>
                                    Recommendations:{" "}
                                    {review.recommendations.length}
                                </p>
                            </>
                        ) : (
                            <UnpublishedStatus />
                        )}
                    </StatusCard>

                    {pendingApprovals.length > 0 && (
                        <div className="md:col-span-2 xl:col-span-4">
                            <StatusCard title="Pending Decisions">
                                <div className="space-y-4">
                                    {pendingApprovals.map((approval) => (
                                        <ApprovalCard
                                            key={approval.identifier}
                                            approval={approval}
                                        />
                                    ))}
                                </div>
                            </StatusCard>
                        </div>
                    )}
                    </div>
                    {info && (
                        <InstallContainerValidationPanel
                            capability={info.install_container}
                            validation={null}
                            error={null}
                        />
                    )}
                </>
            )}
        </section>
    );
}
