import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { atlas } from "../api/atlas";
import {
    disabledNavigationItems,
    navigationItemForPath,
    primaryNavigationItems,
    routeContextForPath,
} from "../app/navigation";
import { StatusBadge } from "../components/StatusBadge";

/**
 * Mission Control 2.0 responsive application shell.
 *
 * - Persistent desktop navigation sidebar (lg and up).
 * - Compact mobile top bar with an openable navigation drawer that never
 *   consumes desktop-sidebar width at narrow viewports.
 * - Shared branding header with the current route/page context and the
 *   Atlas Core release status.
 * - A single `NavigationList` renders both the desktop sidebar and the
 *   mobile drawer from the shared metadata in `app/navigation.ts`, so the
 *   two surfaces cannot drift apart.
 *
 * Presentation-only: no authority, admission, or execution semantics are
 * decided here. The release value comes from the existing authoritative
 * Atlas Core API and degrades to "Release unavailable" when it is missing.
 */

type NavigationListProps = {
    /** Called after a navigation link is activated (mobile drawer close). */
    onNavigate?: () => void;
};

function NavigationList({ onNavigate }: NavigationListProps) {
    const enabledItems = primaryNavigationItems.filter((item) => item.enabled);

    return (
        <ul
            className={[
                "flex flex-col gap-1 px-3 py-5",
                onNavigate ? "min-h-full" : "",
            ].join(" ")}
        >
            {enabledItems.map((item) => (
                <li key={item.path}>
                    <NavLink
                        to={item.path}
                        end={item.end}
                        onClick={onNavigate}
                        className={({ isActive }) =>
                            [
                                "mc-focusable mc-transition flex items-center gap-3 rounded-mc-md px-3 py-3 text-sm font-medium lg:py-2.5",
                                isActive
                                    ? "bg-mc-primary-muted text-mc-primary-strong"
                                    : "text-mc-text-muted hover:bg-mc-surface-elevated hover:text-mc-text-primary",
                            ].join(" ")
                        }
                    >
                        {({ isActive }) => (
                            <>
                                <span
                                    aria-hidden="true"
                                    className={[
                                        "h-2 w-2 shrink-0 rounded-full",
                                        isActive
                                            ? "bg-mc-primary shadow-[0_0_8px_rgba(96,165,250,0.7)]"
                                            : "bg-mc-border",
                                    ].join(" ")}
                                />
                                <span className="min-w-0 truncate">
                                    {item.label}
                                </span>
                            </>
                        )}
                    </NavLink>
                </li>
            ))}
            {disabledNavigationItems.map((item) => (
                <li
                    key={item.path}
                    className="mc-disabled flex items-center gap-3 rounded-mc-md px-3 py-3 text-sm font-medium lg:py-2.5"
                >
                    <span
                        aria-hidden="true"
                        className="h-2 w-2 shrink-0 rounded-full bg-mc-disabled-muted"
                    />
                    <span className="min-w-0 truncate">{item.label}</span>
                    <span className="ml-auto text-[10px] uppercase tracking-wider text-mc-text-disabled">
                        Soon
                    </span>
                </li>
            ))}
        </ul>
    );
}

function Brand() {
    return (
        <div className="flex min-w-0 items-center gap-3">
            <span
                aria-hidden="true"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-mc-md border border-mc-border-subtle bg-mc-surface-elevated text-xs font-bold tracking-widest text-mc-primary-strong"
            >
                A
            </span>
            <div className="min-w-0">
                <p className="truncate text-sm font-bold tracking-[0.22em] text-mc-text-primary">
                    ATLAS
                </p>
                <p className="truncate text-[11px] text-mc-text-muted">
                    Mission Control 2.0
                </p>
            </div>
        </div>
    );
}

function ReleaseFooter({ release }: { release: string | null }) {
    return (
        <div className="border-t border-mc-divider px-4 py-4 sm:px-6 sm:py-5">
            <div className="flex flex-col items-start gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-mc-text-muted">
                    Atlas Core
                </span>
                <StatusBadge status={release ? "Release available" : "unavailable"} />
            </div>
            <p className="mt-2 truncate text-xs text-mc-text-secondary">
                {release ?? "Release unavailable"}
            </p>
        </div>
    );
}

export function MainLayout() {
    const [release, setRelease] = useState<string | null>(null);
    const [mobileNavOpen, setMobileNavOpen] = useState(false);

    const menuButtonRef = useRef<HTMLButtonElement>(null);
    const dialogRef = useRef<HTMLDivElement>(null);
    const location = useLocation();

    const [previousLocation, setPreviousLocation] = useState(location);
    // Reset on every history entry, including search/hash changes. Returning
    // to an earlier URL must never resurrect an old open drawer.
    if (previousLocation !== location) {
        setPreviousLocation(location);
        setMobileNavOpen(false);
    }

    useEffect(() => {
        const desktop = window.matchMedia("(min-width: 64rem)");
        const closeOnDesktop = () => {
            if (desktop.matches) setMobileNavOpen(false);
        };
        desktop.addEventListener("change", closeOnDesktop);
        return () => desktop.removeEventListener("change", closeOnDesktop);
    }, []);

    useEffect(() => {
        let active = true;

        void atlas
            .get<{ release: string }>("")
            .then((response) => {
                if (!active) {
                    return;
                }
                const candidate = response.data?.release;
                setRelease(
                    typeof candidate === "string" && candidate.trim().length > 0
                        ? candidate
                        : null,
                );
            })
            .catch(() => {
                if (active) {
                    setRelease(null);
                }
            });

        return () => {
            active = false;
        };
    }, []);

    // When the drawer opens, move focus to the first navigation link so
    // keyboard users land inside the dialog.
    useEffect(() => {
        if (!mobileNavOpen) {
            return;
        }
        dialogRef.current
            ?.querySelector<HTMLAnchorElement>("a[href]")
            ?.focus();
    }, [mobileNavOpen]);

    // Lock background scroll while the mobile drawer is open.
    useEffect(() => {
        if (!mobileNavOpen) {
            return;
        }
        const previous = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = previous;
        };
    }, [mobileNavOpen]);

    // Escape closes the mobile drawer and restores focus to the trigger.
    useEffect(() => {
        if (!mobileNavOpen) {
            return;
        }
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Tab") {
                const controls = dialogRef.current?.querySelectorAll<HTMLElement>("button, a[href]");
                const first = controls?.[0];
                const last = controls?.[controls.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last?.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first?.focus();
                }
            }
            if (event.key === "Escape") {
                event.preventDefault();
                setMobileNavOpen(false);
                queueMicrotask(() => menuButtonRef.current?.focus());
            }
        };
        window.addEventListener("keydown", onKeyDown);
        return () => {
            window.removeEventListener("keydown", onKeyDown);
        };
    }, [mobileNavOpen]);

    const openMobileNav = () => {
        setMobileNavOpen(true);
    };

    const closeMobileNav = (restoreFocus: boolean) => {
        setMobileNavOpen(false);
        if (restoreFocus) {
            queueMicrotask(() => menuButtonRef.current?.focus());
        }
    };

    const contextLabel = navigationItemForPath(
        primaryNavigationItems,
        location.pathname,
    )?.label ?? routeContextForPath(location.pathname);

    return (
        <div className="mc-app-shell">
            <header inert={mobileNavOpen} className="mc-shell-header sticky top-0 z-40 backdrop-blur">
                <div className="flex min-h-14 min-w-0 flex-wrap items-center gap-2 px-3 py-2 sm:gap-3 sm:px-4">
                    <button
                        ref={menuButtonRef}
                        type="button"
                        onClick={openMobileNav}
                        aria-expanded={mobileNavOpen}
                        aria-controls={
                            mobileNavOpen ? "mc-mobile-navigation" : undefined
                        }
                        className="mc-control mc-focusable inline-flex h-9 w-9 shrink-0 items-center justify-center lg:hidden"
                    >
                        <span className="sr-only">Open navigation</span>
                        <svg
                            viewBox="0 0 24 24"
                            className="h-5 w-5"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            aria-hidden="true"
                        >
                            <path strokeLinecap="round" d="M4 6h16M4 12h16M4 18h16" />
                        </svg>
                    </button>

                    <Brand />

                    {contextLabel && (
                        <span
                            data-testid="mc-context"
                            aria-label={`Current page: ${contextLabel}`}
                            className="order-last w-full min-w-0 truncate rounded-mc-sm sm:order-none sm:w-auto border border-mc-border-subtle bg-mc-surface-muted px-2 py-1 text-xs font-medium text-mc-text-secondary"
                        >
                            {contextLabel}
                        </span>
                    )}

                    <div className="ml-auto hidden shrink-0 items-center gap-2 sm:flex sm:gap-3">
                        <StatusBadge
                            status={release ? "Release available" : "unavailable"}
                        />
                    </div>
                </div>
            </header>

            {mobileNavOpen && (
                <div className="fixed inset-0 z-50 lg:hidden">
                    <div
                        aria-hidden="true"
                        data-testid="mc-mobile-overlay"
                        onClick={() => closeMobileNav(true)}
                        className="absolute inset-0 bg-mc-app/80"
                    />
                    <div
                        ref={dialogRef}
                        id="mc-mobile-navigation"
                        role="dialog"
                        aria-modal="true"
                        aria-label="Mission Control navigation"
                        className="mc-surface absolute inset-y-0 left-0 flex w-full max-w-(--width-mc-mobile-drawer) flex-col"
                    >
                        <div className="flex items-center justify-between gap-3 border-b border-mc-divider px-4 py-4">
                            <Brand />
                            <button
                                type="button"
                                onClick={() => closeMobileNav(true)}
                                aria-label="Close navigation"
                                className="mc-control mc-focusable inline-flex h-9 w-9 shrink-0 items-center justify-center"
                            >
                                <span className="sr-only">Close navigation</span>
                                <svg
                                    viewBox="0 0 24 24"
                                    className="h-5 w-5"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    aria-hidden="true"
                                >
                                    <path
                                        strokeLinecap="round"
                                        d="M6 6l12 12M18 6L6 18"
                                    />
                                </svg>
                            </button>
                        </div>

                        <nav
                            aria-label="Primary"
                            className="min-h-0 flex-1 overflow-y-auto"
                        >
                            <NavigationList
                                onNavigate={() => closeMobileNav(true)}
                            />
                        </nav>

                        <ReleaseFooter release={release} />
                    </div>
                </div>
            )}

            <div inert={mobileNavOpen} className="grid min-h-[calc(100dvh-3.5rem)] lg:grid-cols-[var(--width-mc-sidebar)_minmax(0,1fr)]">
                <aside
                    aria-label="Primary sidebar"
                    className="hidden border-r border-mc-border-subtle bg-mc-surface lg:sticky lg:top-14 lg:block lg:h-[calc(100vh-3.5rem)]"
                >
                    <div className="flex h-full flex-col">
                        <nav
                            aria-label="Primary"
                            className="flex-1 overflow-y-auto"
                        >
                            <NavigationList />
                        </nav>
                        <ReleaseFooter release={release} />
                    </div>
                </aside>

                <div className="mc-main-content min-w-0">
                    <Outlet />
                </div>
            </div>
        </div>
    );
}
