import type { InstallationPlan, InstallationPlanBlockerCode, InstallationPlanStatus } from "../../types/installationPlan";
import { ProspectiveDestinationReview } from "./ProspectiveDestinationReview";

const label = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

const PLAN_STATUS_LABELS: Record<InstallationPlanStatus, string> = {
    conflicted: "Evidence conflicts",
    missing_deployment_artifact: "Deployment file missing",
    incompatible: "Requirements do not match",
    stale_evidence: "Evidence is out of date",
    insufficient_information: "More information needed",
    plan_ready_for_review: "Ready for review",
};

const BLOCKER_LABELS: Record<InstallationPlanBlockerCode, string> = {
    missing_deployment_binding: "Deployment setup is not connected",
    missing_deployment_artifact: "No supported deployment file was found",
    invalid_deployment_artifact: "The deployment file could not be read",
    unsafe_deployment_artifact: "The deployment file needs a safety review",
    unknown_deployment_artifact: "The deployment file could not be checked",
    missing_immutable_image_identity: "The image has no fixed version identity",
    mutable_image_reference: "The image reference can change over time",
    untrusted_evidence: "The image evidence is not trusted",
    image_conflict: "Image reports disagree",
    image_mismatch: "The image does not match the selected release",
    unknown_image_state: "The image status could not be confirmed",
    missing_accepted_evidence: "Required image evidence is missing",
    stale_evidence: "Evidence is out of date",
    malformed_evidence: "Evidence could not be read",
    provenance_conflict: "Evidence sources disagree",
    incompatible_application_environment: "Application requirements do not match",
    unknown_compatibility: "Compatibility could not be confirmed",
    missing_prerequisite: "A required prerequisite is missing",
    missing_prerequisite_fact: "A required fact is not available",
    missing_target_identity: "The selected destination could not be confirmed",
    required_operator_confirmation: "A review note remains",
    malformed_source_fact: "A source fact could not be read",
};

const RISK_LABELS: Record<InstallationPlan["risks"][number]["code"], string> = {
    evidence_approaching_expiry: "Some evidence expires soon",
    compatibility_warning: "Compatibility needs review",
};

export function InstallationPlanReview({
    plan,
    isLoading,
    unavailable,
    csrfToken = null,
}: {
    plan: InstallationPlan | null;
    isLoading: boolean;
    unavailable: boolean;
    csrfToken?: string | null;
}) {
    return (
        <section aria-labelledby="installation-plan-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 id="installation-plan-heading" className="text-xl font-semibold text-white">Installation plan review</h2>
            <p className="mt-1 text-sm text-slate-400">Review what is known, what is missing, and what still needs attention.</p>
            {isLoading && <p className="mt-4 text-sm text-slate-400">Loading installation plan…</p>}
            {!isLoading && unavailable && <p role="status" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">Installation plan is currently unavailable.</p>}
            {!isLoading && !unavailable && plan && <><PlanDetails plan={plan} /><ProspectiveDestinationReview plan={plan} csrfToken={csrfToken} /></>}
        </section>
    );
}

function PlanDetails({ plan }: { plan: InstallationPlan }) {
    const nullable = (value: string | null) => value ?? "None";
    const visibleBlockers = plan.blockers.filter((blocker) => blocker.code !== "required_operator_confirmation"
        || !plan.required_operator_confirmations.some((confirmation) => confirmation.subject === blocker.subject));
    const reviewCount = plan.required_operator_confirmations.length;
    const reviewSummary = reviewCount > 0 ? `${reviewCount} review note${reviewCount === 1 ? "" : "s"}` : null;
    const unresolvedSummary = [
        visibleBlockers.length > 0 ? `${visibleBlockers.length} issue${visibleBlockers.length === 1 ? "" : "s"} ${visibleBlockers.length === 1 ? "blocks" : "block"} this plan` : null,
        reviewSummary,
    ].filter(Boolean).join("; ");
    return (
        <div className="mt-5 space-y-5">
            <div className={`rounded-lg border p-4 ${plan.blockers.length === 0 ? "border-blue-500/30 bg-blue-500/10" : "border-amber-500/30 bg-amber-500/10"}`}>
                <p className="font-semibold text-slate-100">{PLAN_STATUS_LABELS[plan.status]}</p>
                <p className="mt-1 text-sm text-slate-300">
                    {plan.status === "plan_ready_for_review"
                        ? `${reviewSummary ? `${reviewSummary}. ` : ""}This plan does not approve or start installation.`
                        : `${unresolvedSummary || "The available evidence needs review"}. Installation cannot start.`}
                </p>
            </div>
            <ReviewList title="What blocks this plan" empty="No blocking issues reported." rows={visibleBlockers.map((row) => `${BLOCKER_LABELS[row.code]} — ${subjectDescription(plan, row.subject)}`)} />
            <ReviewList title="Items to review" empty="No review notes." rows={plan.required_operator_confirmations.map((row) => confirmationDescription(plan, row))} />
            <ReviewList title="Risks to review" empty="No risks reported." rows={plan.risks.map((row) => `${label(row.severity)} priority · ${RISK_LABELS[row.code]}`)} />
            <details className="rounded-lg border border-slate-700 p-4">
                <summary className="cursor-pointer text-sm font-semibold text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-300">More plan details</summary>
                <div className="mt-4 space-y-5">
                    <ReviewList title="Missing facts" empty="No missing facts." rows={plan.missing_facts.map((row) => `${label(row.code)} — ${subjectDescription(plan, row.subject)}`)} />
                    <ReviewList title="Compatibility" empty="No compatibility records." rows={plan.compatibility.map((row) => `Environment: ${row.environment} · Result: ${label(row.result)} · Reason code: ${row.reason_code}`)} />
                    <ReviewList title="Risk details" empty="No risk details." rows={plan.risks.map((row) => `Risk code: ${row.code} · Subject: ${row.subject}`)} />
                    <ReviewList title="Prerequisites" empty="No prerequisites listed." rows={plan.prerequisites.map((row) => `Kind: ${row.kind} · State: ${row.state} · Description: ${row.description}`)} />
                    <ReviewList title="Relationships" empty="No relationships listed." rows={plan.relationships.map((row) => `Kind: ${row.kind} · Item: ${row.item_id} · Required: ${row.required ? "Yes" : "No"} · Minimum version: ${nullable(row.minimum_version)} · Maximum version: ${nullable(row.maximum_version)}`)} />
                    <ReviewList title="Assumptions" empty="No assumptions listed." rows={plan.assumptions.map((row) => `Kind: ${row.kind} · Statement: ${assumptionDescription(plan, row.assumption_id) ?? row.statement}`)} />
                </div>
            </details>
            <details className="rounded-lg border border-slate-700 p-4">
                <summary className="cursor-pointer text-sm font-semibold text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-300">Plan identity and evidence</summary>
                <div className="mt-4 space-y-5">
                    <dl className="grid gap-3 text-sm sm:grid-cols-2">
                        <Value name="Fingerprint algorithm" value={plan.fingerprint.algorithm} />
                        <Value name="Fingerprint canonicalization" value={plan.fingerprint.canonicalization} />
                        <Value name="Plan fingerprint" value={plan.fingerprint.value} />
                        <Value name="Fingerprint purpose" value="Integrity linkage only — not approval" />
                        <Value name="Application item" value={plan.application.item_id} />
                        <Value name="Application catalog entry ID" value={plan.application.catalog_entry_id} />
                        <Value name="Application display name" value={plan.application.display_name} />
                        <Value name="Application release version" value={nullable(plan.application.release_version)} />
                        <Value name="Deployment artifact state" value={label(plan.deployment_artifact.state)} />
                        <Value name="Deployment artifact kind" value={plan.deployment_artifact.kind} />
                        <Value name="Deployment repository path" value={nullable(plan.deployment_artifact.repository_path)} />
                        <Value name="Deployment artifact service" value={nullable(plan.deployment_artifact.service)} />
                        <Value name="Deployment artifact content digest" value={nullable(plan.deployment_artifact.content_digest)} />
                        <Value name="Image state" value={label(plan.image.state)} />
                        <Value name="Image reference" value={nullable(plan.image.reference)} />
                        <Value name="Image digest" value={nullable(plan.image.digest)} />
                        <Value name="Image release version" value={nullable(plan.image.release_version)} />
                        <Value name="Schema" value={plan.schema_version} />
                    </dl>
                    <ReviewList title="Accepted evidence" empty="No accepted evidence records." rows={plan.accepted_evidence.map((row) => `Evidence ID: ${row.evidence_id} · Source class: ${row.source_class} · Source ID: ${row.source_id} · Subject: ${row.subject} · Claim: ${row.claim} · Immutable identity: ${row.immutable_identity} · Observed at: ${nullable(row.observed_at)} · Attested at: ${row.attested_at} · Freshness window seconds: ${row.freshness_window_seconds} · Trust: ${row.trust}`)} />
                    <ReviewList title="Provenance" empty="No provenance records." rows={plan.provenance.map((row) => `Claim: ${row.claim} · Source class: ${row.source_class} · Source ID: ${row.source_id} · Immutable identity: ${row.immutable_identity} · Observed at: ${nullable(row.observed_at)} · Attested at: ${nullable(row.attested_at)}`)} />
                    <ReviewList title="Exact review references" empty="No blocker or confirmation references." rows={[
                        ...plan.blockers.map((row) => `Blocker code: ${row.code} · Subject ID: ${row.subject}`),
        ...plan.required_operator_confirmations.map((row) => `Confirmation code: ${row.code} · Subject ID: ${row.subject} · Exact prompt: ${row.prompt}`),
                        ...plan.prerequisites.map((row) => `Prerequisite ID: ${row.prerequisite_id}`),
                        ...plan.assumptions.map((row) => `Assumption ID: ${row.assumption_id} · Exact statement: ${row.statement}`),
                    ]} />
                </div>
            </details>
        </div>
    );
}

function ReviewList({ title, empty, rows }: { title: string; empty: string; rows: string[] }) {
    return <div><h3 className="text-sm font-semibold text-slate-200">{title}</h3>{rows.length === 0 ? <p className="mt-2 text-sm text-slate-500">{empty}</p> : <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">{rows.map((row, index) => <li className="break-words" key={`${index}-${row}`}>{row}</li>)}</ul>}</div>;
}

function assumptionDescription(plan: InstallationPlan, assumptionId: string) {
    const assumption = plan.assumptions.find((row) => row.assumption_id === assumptionId);
    if (!assumption) return null;
    const related = plan.prerequisites.filter((row) => assumption.statement.includes(row.prerequisite_id));
    if (related.length === 0) return assumption.statement;
    let statement = assumption.statement;
    for (const prerequisite of related) {
        statement = statement.replace(` for prerequisite ${prerequisite.prerequisite_id}`, "");
    }
    return `${statement} Related prerequisite: ${related.map((row) => row.description).join("; ")}`;
}

function subjectDescription(plan: InstallationPlan, subject: string) {
    if (subject === plan.application.item_id || subject === plan.application.catalog_entry_id) return plan.application.display_name;
    return plan.prerequisites.find((row) => row.prerequisite_id === subject)?.description
        ?? assumptionDescription(plan, subject)
        ?? subject;
}

function confirmationDescription(
    plan: InstallationPlan,
    row: InstallationPlan["required_operator_confirmations"][number],
) {
    const prerequisite = plan.prerequisites.find((item) => item.prerequisite_id === row.subject);
    if (prerequisite) return `Review prerequisite — ${prerequisite.description}. This note does not approve or authorize an action.`;
    const assumption = plan.assumptions.find((item) => item.assumption_id === row.subject);
    if (assumption) return `Review assumption — ${assumptionDescription(plan, assumption.assumption_id)}. This note does not approve or authorize an action.`;
    const prompt = row.prompt.replace(/^(?:confirm|review)\s+/i, "").replace(/; this does not approve or authorize any action\.$/i, "");
    const subject = row.code === "confirm_risk" ? "risk" : row.code === "accept_assumption" ? "assumption" : "prerequisite";
    return `Review ${subject}: ${prompt}. This note does not approve or authorize an action.`;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
