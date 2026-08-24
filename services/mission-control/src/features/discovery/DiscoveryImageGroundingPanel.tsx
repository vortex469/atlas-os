import type {
    DiscoveryImageEvidenceSourceClass,
    DiscoveryImageGroundingProjection,
    DiscoveryImageGroundingStatus,
} from "../../types/discovery";

export type ImageGroundingErrorKind = "not_found" | "source_unavailable" | "unavailable";

const STATUS_COPY: Record<DiscoveryImageGroundingStatus, { label: string; detail: string }> = {
    grounded: {
        label: "Grounded",
        detail: "The observed immutable image matches accepted release evidence.",
    },
    no_deployment_binding: {
        label: "No deployment binding",
        detail: "No reviewed deployment binding is available for this item.",
    },
    no_strict_release_version: {
        label: "No strict release version",
        detail: "The item does not provide a strict release version for comparison.",
    },
    no_repository_observation: {
        label: "No repository observation",
        detail: "No repository image observation is available.",
    },
    observation_mismatch: {
        label: "Observation mismatch",
        detail: "The repository observation does not match the deployment binding.",
    },
    mutable_observation: {
        label: "Mutable observation",
        detail: "The observed image is mutable and cannot be grounded to an immutable digest.",
    },
    no_image_release_evidence: {
        label: "No image release evidence",
        detail: "No accepted image-release evidence is available.",
    },
    evidence_not_trusted: {
        label: "Evidence not trusted",
        detail: "Available evidence does not meet an accepted provenance class.",
    },
    evidence_version_mismatch: {
        label: "Evidence version mismatch",
        detail: "Accepted evidence does not match the strict release version.",
    },
    repository_identity_mismatch: {
        label: "Repository identity mismatch",
        detail: "The observed repository identity does not match accepted evidence.",
    },
    digest_mismatch: {
        label: "Digest mismatch",
        detail: "The observed image digest does not match accepted evidence.",
    },
    conflicted: {
        label: "Conflicted",
        detail: "Accepted evidence conflicts; image grounding must not be treated as established.",
    },
};

const SOURCE_STYLES: Record<DiscoveryImageEvidenceSourceClass, string> = {
    curated: "border-blue-400/40 bg-blue-500/10 text-blue-200",
    registry_attested: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
    upstream_signed: "border-violet-400/40 bg-violet-500/10 text-violet-200",
};

const SOURCE_LABELS: Record<DiscoveryImageEvidenceSourceClass, string> = {
    curated: "CURATED",
    registry_attested: "REGISTRY_ATTESTED",
    upstream_signed: "UPSTREAM_SIGNED",
};

export function DiscoveryImageGroundingPanel({
    projection,
    isLoading,
    errorKind,
}: {
    projection: DiscoveryImageGroundingProjection | null;
    isLoading: boolean;
    errorKind: ImageGroundingErrorKind | null;
}) {
    return (
        <section aria-labelledby="image-grounding-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 id="image-grounding-heading" className="text-xl font-semibold text-white">Image grounding</h2>
            <p className="mt-1 text-sm text-slate-400">
                Image grounding is advisory and grants no deployment or execution authority.
            </p>

            {isLoading && <p className="mt-4 text-sm text-slate-400">Loading image-grounding context…</p>}
            {!isLoading && errorKind && <UnavailableState kind={errorKind} />}
            {!isLoading && !errorKind && !projection && (
                <UnavailableState kind="unavailable" />
            )}
            {!isLoading && !errorKind && projection && <ProjectionDetails projection={projection} />}
        </section>
    );
}

function UnavailableState({ kind }: { kind: ImageGroundingErrorKind }) {
    const copy = kind === "not_found"
        ? "Item grounding projection unavailable or not found."
        : kind === "source_unavailable"
          ? "Image grounding is currently unavailable due to a local source or read failure."
          : "Image grounding is currently unavailable.";
    return <p role="status" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">{copy}</p>;
}

function ProjectionDetails({ projection }: { projection: DiscoveryImageGroundingProjection }) {
    const status = STATUS_COPY[projection.status];
    const grounded = projection.status === "grounded";
    return (
        <div className="mt-5 space-y-5">
            <div className={`rounded-lg border p-4 ${grounded ? "border-emerald-500/30 bg-emerald-500/10" : "border-amber-500/30 bg-amber-500/10"}`}>
                <p className={`font-semibold ${grounded ? "text-emerald-200" : "text-amber-200"}`}>{status.label}</p>
                <p className={`mt-1 text-sm ${grounded ? "text-emerald-200/80" : "text-amber-200/80"}`}>{status.detail}</p>
            </div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <Value label="Release version" value={projection.release_version ?? "Not available"} />
                <Value label="Deployment method" value={projection.deployment_binding?.deployment_method ?? "No deployment binding"} />
                <Value label="Compose service" value={projection.deployment_binding?.compose_service ?? "Not available"} />
                <Value label="Compose file" value={projection.deployment_binding?.compose_file ?? "Not available"} />
                <Value label="Observed image" value={projection.observed_image?.image_reference ?? "No repository observation"} />
                <Value label="Observed digest" value={projection.observed_image?.image_digest ?? "Not available"} />
            </dl>
            <div>
                <h3 className="text-sm font-semibold text-slate-200">Accepted evidence</h3>
                {projection.accepted_evidence.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-500">No accepted image-release evidence.</p>
                ) : (
                    <ol className="mt-3 space-y-3">
                        {projection.accepted_evidence.map((row, index) => (
                            <li key={`${row.source_class}-${row.source_id}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950 p-4">
                                <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold tracking-wide ${SOURCE_STYLES[row.source_class]}`}>
                                    {SOURCE_LABELS[row.source_class]}
                                </span>
                                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                                    <Value label="Source ID" value={row.source_id} />
                                    <Value label="Attested at" value={row.attested_at} />
                                    <Value label="Release" value={row.release_version} />
                                    <Value label="Image" value={row.image_reference} />
                                    <div className="sm:col-span-2"><Value label="Digest" value={row.image_digest} /></div>
                                </dl>
                            </li>
                        ))}
                    </ol>
                )}
            </div>
        </div>
    );
}

function Value({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
