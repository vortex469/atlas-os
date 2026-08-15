import { Link } from "react-router-dom";

import type { DiscoveryProposalNavigation } from "../../types/discovery";
import { resolveProposalNavigation } from "./proposalNavigation";

const destinationLabels = {
    discovery_detail: "Review Discovery item",
    compatibility_review: "Review compatibility evidence",
    operator_maintenance_selection: "Continue to maintenance selection",
} as const;

function label(value: string): string {
    return value.replaceAll("_", " ").replace(/\b\w/g, (part) => part.toUpperCase());
}

function isReviewOnly(proposal: DiscoveryProposalNavigation): boolean {
    return proposal.status !== "current"
        || !proposal.actionable_navigation
        || proposal.destination_kind !== "operator_maintenance_selection";
}

export function DiscoveryProposalCard({
    proposal,
    showNavigation = true,
}: {
    proposal: DiscoveryProposalNavigation;
    showNavigation?: boolean;
}) {
    const destination = resolveProposalNavigation(proposal);
    const reviewOnly = isReviewOnly(proposal);
    const to = destination.kind === "operator_maintenance_selection"
        ? { pathname: "/operations/request" }
        : { pathname: `/discovery/items/${encodeURIComponent(destination.itemId ?? proposal.catalog_item_id)}` };
    const state = destination.kind === "operator_maintenance_selection"
        ? { proposalId: destination.proposalId }
        : undefined;

    const labelDestination = reviewOnly
        && proposal.destination_kind === "operator_maintenance_selection"
        ? "discovery_detail"
        : proposal.destination_kind;

    return (
        <article className="space-y-4 rounded-xl border border-slate-700 bg-slate-950/60 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">Advisory proposal</p>
                    <h3 className="mt-1 font-semibold text-slate-100">{proposal.catalog_item_id}</h3>
                    <p className="mt-1 break-all text-xs text-slate-500">{proposal.proposal_id}</p>
                </div>
                <span className="rounded-full border border-slate-600 px-2.5 py-1 text-xs text-slate-200">
                    Status: {label(proposal.status)}
                </span>
            </div>

            <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <Fact name="Reason" value={label(proposal.reason)} />
                <Fact name="Compatibility" value={label(proposal.compatibility_status)} />
                <Fact name="Destination" value={label(proposal.destination_kind)} />
                <Fact name="Catalog source" value={label(proposal.catalog_source_type)} />
                <Fact name="Finding references" value={String(proposal.finding_reference_count)} />
                <Fact name="Evidence references" value={String(proposal.evidence_reference_count)} />
                <Fact name="Generated" value={new Date(proposal.generated_at).toLocaleString()} />
                <Fact name="Expires" value={new Date(proposal.expires_at).toLocaleString()} />
                {proposal.intent_hint && <Fact name="Intent hint" value={proposal.intent_hint} />}
            </dl>

            {proposal.target_hints.length > 0 && (
                <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">Non-authoritative target hints</p>
                    <ul className="mt-2 space-y-1 text-xs text-slate-400">
                        {proposal.target_hints.map((hint, index) => (
                            <li key={`${hint.catalog_target_id ?? ""}-${hint.provider_hint ?? ""}-${hint.resource_type_hint ?? ""}-${index}`}>
                                {[hint.catalog_target_id, hint.provider_hint, hint.resource_type_hint].filter(Boolean).join(" / ")}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {reviewOnly ? (
                <p role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                    Review only: operational navigation is disabled because this proposal is {label(proposal.status).toLowerCase()} ({label(proposal.reason).toLowerCase()}).
                </p>
            ) : (
                <p className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-3 text-sm text-blue-200">
                    This proposal is advisory. Atlas will re-check your permission and reload current capability descriptors, the authoritative selector, and its fingerprint. Proposal hints do not authorize an action.
                </p>
            )}

            {showNavigation && <Link
                to={to}
                state={state}
                aria-label={`${destinationLabels[labelDestination]} for ${proposal.catalog_item_id}`}
                className="inline-flex rounded-lg border border-blue-400/40 px-3 py-2 text-sm font-semibold text-blue-200 hover:bg-blue-400/10"
            >
                {destinationLabels[labelDestination]}
            </Link>}
        </article>
    );
}

function Fact({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-slate-500">{name}</dt><dd className="text-slate-200">{value}</dd></div>;
}
