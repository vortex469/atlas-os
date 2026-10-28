/**
 * Mission Control 2.0 shared navigation metadata.
 *
 * This is the single source of truth for the shell's primary navigation
 * labels and destinations. The desktop sidebar and compact mobile drawer
 * both render from this list, so the two surfaces cannot drift apart.
 *
 * Presentation-only: this module never decides eligibility, admission, or
 * execution authority. Only destinations with a real route belong in the
 * visible menu; planned areas stay out until they are usable.
 *
 * Task 5 (navigation refinement) can extend `NavigationItem` with sections,
 * icons, and keyboard shortcuts without touching the shell markup.
 */

export type NavigationItem = {
    label: string;
    path: string;
    /**
     * NavLink exact-match flag. Only the root route needs `end` so that
     * `/operations` does not keep the Overview link active.
     */
    end?: boolean;
    /** Short label for compact mobile navigation, when the label is long. */
    shortLabel?: string;
};

export const primaryNavigationItems: NavigationItem[] = [
    {
        label: "Overview",
        path: "/",
        end: true,
    },
    {
        label: "Action history",
        path: "/operations",
    },
    {
        label: "Maintenance history",
        path: "/operations/history",
        shortLabel: "History",
    },
    {
        label: "Request maintenance",
        path: "/operations/request",
    },
    {
        label: "Catalog",
        path: "/discovery",
    },
    {
        label: "Change proposals",
        path: "/execution-candidates",
        shortLabel: "Proposals",
    },
    {
        label: "Workflows",
        path: "/workflows",
    },
    {
        label: "Deployment analysis",
        path: "/forge",
    },
];

/**
 * Returns the most specific destination that owns the given path.
 * Used to surface the current route/page context in the shell header.
 * Longest prefix wins, so `/operations/history` resolves to
 * Maintenance history rather than its Action history parent.
 */
export function navigationItemForPath(
    items: NavigationItem[],
    pathname: string,
): NavigationItem | undefined {
    let best: NavigationItem | undefined;
    for (const item of items) {
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
    if (pathname === "/providers") return "Providers";
    if (pathname.startsWith("/providers/")) return "Provider";
    if (pathname.startsWith("/installation/")) return "Installation readiness review";
    if (pathname.startsWith("/candidate-planning/")) return "Candidate planning";
    if (pathname === "/operator/login") return "Operator login";
    return "Page not found";
}
