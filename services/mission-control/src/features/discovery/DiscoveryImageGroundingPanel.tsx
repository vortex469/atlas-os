import type {
    DiscoveryImageEvidenceSourceClass,
    DiscoveryImageGroundingProjection,
    DiscoveryImageGroundingStatus,
} from "../../types/discovery";

export type ImageGroundingErrorKind = "not_found" | "source_unavailable" | "unavailable";

const STATUS_COPY: Record<DiscoveryImageGroundingStatus, { label: string; detail: string }> = {
    grounded: {
        label: "Image matches release evidence",
        detail: "The image Atlas found matches evidence for this release.",
    },
    no_deployment_binding: {
        label: "No deployment mapping",
        detail: "Atlas does not have a saved record of where this item is deployed.",
    },
    no_strict_release_version: {
        label: "Release version unavailable",
        detail: "Atlas cannot compare the image without a supported release version.",
    },
    no_repository_observation: {
        label: "No image found in the repository",
        detail: "Atlas could not find an image reference in the deployment files.",
    },
    observation_mismatch: {
        label: "Image does not match the deployment mapping",
        detail: "The image in the deployment files differs from the saved deployment record.",
    },
    mutable_observation: {
        label: "Image reference can change",
        detail: "This image reference can point to different content, so Atlas cannot verify the exact image.",
    },
    no_image_release_evidence: {
        label: "Release evidence is missing",
        detail: "Atlas has no accepted evidence tying an image to this release.",
    },
    evidence_not_trusted: {
        label: "Evidence source is not accepted",
        detail: "The available evidence is not from a source Atlas accepts for this check.",
    },
    evidence_version_mismatch: {
        label: "Evidence is for a different release",
        detail: "The release listed in the evidence differs from this item's release.",
    },
    repository_identity_mismatch: {
        label: "Image repository does not match",
        detail: "The observed image comes from a different repository than the evidence.",
    },
    digest_mismatch: {
        label: "Image contents do not match",
        detail: "The image contents differ from the image recorded in the evidence.",
    },
    conflicted: {
        label: "Evidence conflicts",
        detail: "The available evidence disagrees, so Atlas cannot verify the image.",
    },
};

const SOURCE_STYLES: Record<DiscoveryImageEvidenceSourceClass, string> = {
    curated: "border-blue-400/40 bg-blue-500/10 text-blue-200",
    registry_attested: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
    upstream_signed: "border-violet-400/40 bg-violet-500/10 text-violet-200",
};

const SOURCE_LABELS: Record<DiscoveryImageEvidenceSourceClass, string> = {
    curated: "Curated catalog",
    registry_attested: "Registry attestation",
    upstream_signed: "Signed upstream release",
};

export function DiscoveryImageGroundingPanel({
    projection,
    isLoading,
    errorKind,
    onRetry,
}: {
    projection: DiscoveryImageGroundingProjection | null;
    isLoading: boolean;
    errorKind: ImageGroundingErrorKind | null;
    onRetry?: () => void;
}) {
    return (
        <section aria-labelledby="image-grounding-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 id="image-grounding-heading" className="text-xl font-semibold text-white">Image check</h2>
            <p className="mt-1 text-sm text-slate-400">
                Read-only check. It does not install, deploy, or run anything.
            </p>

            {isLoading && <p className="mt-4 text-sm text-slate-400">Checking image and release evidence…</p>}
            {!isLoading && errorKind && <UnavailableState kind={errorKind} onRetry={onRetry} />}
            {!isLoading && !errorKind && !projection && (
                <UnavailableState kind="unavailable" onRetry={onRetry} />
            )}
            {!isLoading && !errorKind && projection && <ProjectionDetails projection={projection} />}
        </section>
    );
}

function UnavailableState({ kind, onRetry }: { kind: ImageGroundingErrorKind; onRetry?: () => void }) {
    const copy = kind === "not_found"
        ? "No image check is available for this item."
        : kind === "source_unavailable"
          ? "Atlas could not finish checking the image. Try again."
          : "The image check is unavailable right now.";
    return <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200"><p role="status">{copy}</p>{kind !== "not_found" && onRetry && <button type="button" onClick={onRetry} className="mc-control mc-focusable mt-3 px-3 py-2 font-semibold">Retry image check</button>}</div>;
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
                <Value label="Release" value={projection.release_version ?? "Not available"} />
                <Value label="Image found" value={projection.observed_image?.image_reference ?? "No image found"} />
            </dl>
            <div>
                <h3 className="text-sm font-semibold text-slate-200">Evidence</h3>
                {projection.accepted_evidence.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-400">No accepted release evidence is available.</p>
                ) : (
                    <ol aria-label="Release evidence" className="mt-3 space-y-2">
                        {projection.accepted_evidence.map((row, index) => (
                            <li key={`${row.source_class}-${row.source_id}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                                <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${SOURCE_STYLES[row.source_class]}`}>
                                    {SOURCE_LABELS[row.source_class]}
                                </span>
                                <p className="mt-2 text-sm text-slate-300">Release {row.release_version} · evidence dated {formatUtcTimestamp(row.attested_at)}</p>
                            </li>
                        ))}
                    </ol>
                )}
            </div>
            <details className="rounded-lg border border-slate-800 px-4 py-3 text-sm text-slate-300">
                <summary className="mc-focusable cursor-pointer font-medium">Technical details</summary>
                <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Value label="Deployment method" value={projection.deployment_binding?.deployment_method ?? "No deployment mapping"} />
                    <Value label="Compose service" value={projection.deployment_binding?.compose_service ?? "Not available"} />
                    <Value label="Compose file" value={projection.deployment_binding?.compose_file ?? "Not available"} />
                    <Value label="Observed image digest" value={projection.observed_image?.image_digest ?? "Not available"} />
                </dl>
                {projection.accepted_evidence.length > 0 && <ol aria-label="Detailed release evidence" className="mt-4 space-y-3">
                    {projection.accepted_evidence.map((row, index) => (
                        <li key={`${row.source_class}-${row.source_id}-${index}`} className="rounded-lg border border-slate-800 p-3">
                            <dl className="grid gap-2 sm:grid-cols-2">
                                <Value label="Evidence source" value={SOURCE_LABELS[row.source_class]} />
                                <Value label="Source ID" value={row.source_id} />
                                <Value label="Source class" value={row.source_class} />
                                <Value label="Release" value={row.release_version} />
                                <Value label="Image" value={row.image_reference} />
                                <Value label="Digest" value={row.image_digest} />
                                <Value label="Attestation time (UTC)" value={row.attested_at} />
                            </dl>
                        </li>
                    ))}
                </ol>}
            </details>
        </div>
    );
}

function Value({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Time unavailable";
    return `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
