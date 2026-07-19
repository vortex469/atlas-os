export function createProviderId(name: string): string {
    return name
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

export function normalizeProviderName(value: string | null): string {
    return (value ?? "")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "");
}

export function formatProviderId(providerId: string): string {
    return providerId
        .split("-")
        .filter(Boolean)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

export function providerValuesMatch(
    first: string | null,
    second: string | null,
): boolean {
    return normalizeProviderName(first) === normalizeProviderName(second);
}
