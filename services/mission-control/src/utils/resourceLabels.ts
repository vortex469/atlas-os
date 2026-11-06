const providerLabels: Record<string, string> = {
    homeassistant: "Home Assistant",
    n8n: "n8n",
    opnsense: "OPNsense",
    proxmox: "Proxmox",
};

function humanizeIdentifier(value: string): string {
    return value.trim().replaceAll(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatProviderLabel(value: string | null | undefined): string {
    const normalized = value?.trim().toLowerCase() ?? "";
    if (!normalized || normalized === "unknown") return "Unknown provider";
    return Object.hasOwn(providerLabels, normalized) ? providerLabels[normalized] : humanizeIdentifier(normalized);
}

export function formatResourceTypeLabel(value: string | null | undefined): string {
    const normalized = value?.trim().toLowerCase() ?? "";
    if (normalized === "qemu") return "Virtual machine";
    if (normalized === "lxc") return "Container";
    if (!normalized || normalized === "unknown") return "Resource";
    return humanizeIdentifier(normalized);
}

export function formatResourceTargetLabel(
    providerId: string,
    resourceType: string,
    resourceId: string,
): string {
    const targetId = resourceId.trim() || "unknown ID";
    return `${formatProviderLabel(providerId)} ${formatResourceTypeLabel(resourceType).toLowerCase()} ${targetId}`;
}

export function formatResourceReference(
    providerId: string,
    resourceType: string,
    resourceId: string,
): string {
    return `${providerId}/${resourceType}/${resourceId}`;
}
