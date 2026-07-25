import type { ReactNode } from "react";

import type { AtlasPolicies } from "../types/policies";
import { SectionHeader } from "./SectionHeader";

type ProviderPolicyDetailsProps = {
    providerId: string;
    policies: AtlasPolicies;
};

type PolicyDetail = {
    label: string;
    value: ReactNode;
};

function formatSeverity(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function names(values: string[]): string {
    return values.length > 0 ? values.join(", ") : "None configured";
}

function policyDetails(
    providerId: string,
    policies: AtlasPolicies,
): PolicyDetail[] | null {
    const normalizedId = providerId.replaceAll("_", "-");

    if (normalizedId === "proxmox") {
        const guests = Object.entries(policies.proxmox.guests).map(
            ([vmid, policy]) => `${vmid}: ${policy.expected}`,
        );
        return [
            {
                label: "Guest expectations",
                value: names(guests),
            },
        ];
    }

    if (normalizedId === "docker") {
        const containers = Object.entries(
            policies.docker.containers,
        ).map(
            ([container, policy]) =>
                `${container}: ${policy.expected}`,
        );
        return [
            {
                label: "Container expectations",
                value: names(containers),
            },
        ];
    }

    if (normalizedId === "home-assistant") {
        return [
            {
                label: "Ignored entities",
                value: names(
                    policies.homeassistant.ignored_entities,
                ),
            },
        ];
    }

    if (normalizedId === "opnsense") {
        return [
            {
                label: "Pending update threshold",
                value:
                    policies.opnsense
                        .pending_update_warning_threshold === null
                        ? "Informational only"
                        : `${policies.opnsense.pending_update_warning_threshold} package(s)`,
            },
            {
                label: "Reboot required severity",
                value: formatSeverity(
                    policies.opnsense.reboot_required_severity,
                ),
            },
        ];
    }

    if (normalizedId === "frigate") {
        const cameras = Object.entries(policies.frigate.cameras).map(
            ([camera, policy]) =>
                `${camera}: ${policy.expected}, capture ≥ ${policy.minimum_camera_fps} FPS, process ≥ ${policy.minimum_process_fps} FPS`,
        );
        return [
            {
                label: "Camera expectations",
                value: names(cameras),
            },
            {
                label: "Camera health severity",
                value: formatSeverity(
                    policies.frigate.stalled_camera_severity,
                ),
            },
        ];
    }

    if (normalizedId === "obsidian") {
        return [
            {
                label: "Minimum notes",
                value: policies.obsidian.minimum_note_count,
            },
            {
                label: "Freshness window",
                value:
                    policies.obsidian.stale_after_days === null
                        ? "Disabled"
                        : `${policies.obsidian.stale_after_days} day(s)`,
            },
            {
                label: "Insufficient notes severity",
                value: formatSeverity(
                    policies.obsidian
                        .insufficient_notes_severity,
                ),
            },
            {
                label: "Stale vault severity",
                value: formatSeverity(
                    policies.obsidian.stale_severity,
                ),
            },
            {
                label: "Truncated scan severity",
                value: formatSeverity(
                    policies.obsidian.scan_truncated_severity,
                ),
            },
        ];
    }

    if (normalizedId === "qdrant") {
        return [
            {
                label: "Expected collections",
                value: names(
                    policies.qdrant.expected_collections,
                ),
            },
            {
                label: "Missing collection severity",
                value: formatSeverity(
                    policies.qdrant.missing_collection_severity,
                ),
            },
            {
                label: "Empty instance severity",
                value: formatSeverity(
                    policies.qdrant.empty_instance_severity,
                ),
            },
        ];
    }

    if (normalizedId === "n8n") {
        return [
            {
                label: "Expected active workflows",
                value: names(
                    policies.n8n.expected_active_workflows,
                ),
            },
            {
                label: "Inactive workflow severity",
                value: formatSeverity(
                    policies.n8n.inactive_workflow_severity,
                ),
            },
            {
                label: "Truncated scan severity",
                value: formatSeverity(
                    policies.n8n.scan_truncated_severity,
                ),
            },
            {
                label: "Empty instance severity",
                value: formatSeverity(
                    policies.n8n.empty_instance_severity,
                ),
            },
        ];
    }

    return null;
}

export function ProviderPolicyDetails({
    providerId,
    policies,
}: ProviderPolicyDetailsProps) {
    const details = policyDetails(providerId, policies);

    return (
        <section>
            <SectionHeader
                title="Operational Policy"
                description="Live validated expectations currently enforced for this provider."
            />

            {details === null ? (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                    No provider-specific operational policy is
                    configured.
                </div>
            ) : (
                <dl className="grid gap-px overflow-hidden rounded-lg border border-slate-800 bg-slate-800 sm:grid-cols-2">
                    {details.map((detail) => (
                        <div
                            key={detail.label}
                            className="bg-slate-900 p-5"
                        >
                            <dt className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
                                {detail.label}
                            </dt>
                            <dd className="mt-2 break-words text-sm leading-6 text-slate-200">
                                {detail.value}
                            </dd>
                        </div>
                    ))}
                </dl>
            )}
        </section>
    );
}
