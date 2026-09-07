/**
 * Mission Control 2.0 shared navigation metadata.
 *
 * This is the single source of truth for the shell's primary navigation
 * labels, destinations, and enabled state. The desktop sidebar and the
 * compact mobile navigation both render from `primaryNavigationItems`, so
 * the two surfaces cannot drift apart.
 *
 * Presentation-only: this module never decides eligibility, admission, or
 * execution authority. Disabled entries are placeholders for destinations
 * that do not yet have a real route and authoritative backing
 * implementation; they are rendered inert and must not be activated here.
 *
 * Task 5 (navigation refinement) can extend `NavigationItem` with sections,
 * icons, and keyboard shortcuts without touching the shell markup.
 */

export type NavigationItem = {
    label: string;
    path: string;
    enabled: boolean;
    /**
     * NavLink exact-match flag. Only the root route needs `end` so that
     * `/operations` does not keep the Mission Control link active.
     */
    end?: boolean;
    /** Short label for compact mobile navigation, when the label is long. */
    shortLabel?: string;
};

export const primaryNavigationItems: NavigationItem[] = [
    {
        label: "Mission Control",
        path: "/",
        enabled: true,
        end: true,
    },
    {
        label: "Operations",
        path: "/operations",
        enabled: true,
    },
    {
        label: "Operational History",
        path: "/operations/history",
        enabled: true,
        shortLabel: "History",
    },
    {
        label: "Maintenance",
        path: "/operations/request",
        enabled: true,
    },
    {
        label: "Discovery",
        path: "/discovery",
        enabled: true,
    },
    {
        label: "Execution Candidates",
        path: "/execution-candidates",
        enabled: true,
        shortLabel: "Candidates",
    },
    {
        label: "Workflows",
        path: "/workflows",
        enabled: true,
    },
    {
        label: "Forge",
        path: "/forge",
        enabled: true,
    },
];

/**
 * Disabled future destinations. Kept visible but inert: no backing route or
 * authoritative implementation exists yet, so they are never rendered as
 * links. Do not move them into `primaryNavigationItems` until the route and
 * its authoritative backing implementation exist.
 */
export const disabledNavigationItems: NavigationItem[] = [
    { label: "Knowledge", path: "/knowledge", enabled: false },
    { label: "Developer", path: "/developer", enabled: false },
    { label: "Settings", path: "/settings", enabled: false },
];

/**
 * Returns the most specific enabled destination that owns the given path.
 * Used to surface the current route/page context in the shell header.
 * Longest prefix wins, so `/operations/history` resolves to
 * Operational History rather than its Operations parent.
 */
export function navigationItemForPath(
    items: NavigationItem[],
    pathname: string,
): NavigationItem | undefined {
    let best: NavigationItem | undefined;
    for (const item of items) {
        if (!item.enabled) {
            continue;
        }
        const matches =
            item.path === "/"
                ? pathname === "/"
                : pathname === item.path ||
                  pathname.startsWith(`${item.path}/`);
        if (!matches) {
            continue;
        }
        if (!best || item.path.length > best.path.length) {
            best = item;
        }
    }
    return best;
}

// Existing detail and utility routes that are not primary destinations.
export function routeContextForPath(pathname: string): string {
    if (pathname.startsWith("/providers/")) return "Provider";
    if (pathname.startsWith("/installation/")) return "Installation readiness review";
    if (pathname.startsWith("/candidate-planning/")) return "Candidate planning";
    if (pathname === "/operator/login") return "Operator login";
    return "Mission Control";
}
