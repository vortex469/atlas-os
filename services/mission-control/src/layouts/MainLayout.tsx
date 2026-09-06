import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { atlas } from "../api/atlas";

type NavigationItem = {
    label: string;
    path: string;
    enabled: boolean;
};

const navigationItems: NavigationItem[] = [
    { label: "Mission Control", path: "/", enabled: true },
    { label: "Operations", path: "/operations", enabled: true },
    { label: "Operational History", path: "/operations/history", enabled: true },
    { label: "Maintenance", path: "/operations/request", enabled: true },
    { label: "Discovery", path: "/discovery", enabled: true },
    { label: "Execution Candidates", path: "/execution-candidates", enabled: true },
    { label: "Workflows", path: "/workflows", enabled: true },
    { label: "Forge", path: "/forge", enabled: true },
    { label: "Knowledge", path: "/knowledge", enabled: false },
    { label: "Developer", path: "/developer", enabled: false },
    { label: "Settings", path: "/settings", enabled: false },
];

export function MainLayout() {
    const [release, setRelease] = useState<string | null>(null);

    useEffect(() => {
        let active = true;

        void atlas
            .get<{ release: string }>("")
            .then((response) => {
                if (active) {
                    setRelease(response.data.release);
                }
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

    return (
        <div className="mc-app-shell">
            <div className="grid min-h-screen lg:grid-cols-[15rem_1fr]">
                <aside className="border-r border-mc-border-subtle bg-mc-surface">
                    <div className="flex min-h-screen flex-col">
                        <div className="border-b border-mc-divider px-6 py-6">
                            <p className="text-xl font-bold tracking-[0.25em] text-mc-text-primary">
                                ATLAS
                            </p>
                            <p className="mt-1 text-xs text-mc-text-muted">
                                Operating Console
                            </p>
                        </div>

                        <nav className="flex-1 space-y-1 px-3 py-5">
                            {navigationItems.map((item) =>
                                item.enabled ? (
                                    <NavLink
                                        key={item.path}
                                        to={item.path}
                                        end={item.path === "/"}
                                        className={({ isActive }) =>
                                            [
                                                "mc-focusable mc-transition flex items-center gap-3 rounded-mc-md px-3 py-2.5 text-sm font-medium",
                                                isActive
                                                    ? "bg-mc-primary-muted text-mc-primary-strong"
                                                    : "text-mc-text-muted hover:bg-mc-surface-elevated hover:text-mc-text-primary",
                                            ].join(" ")
                                        }
                                    >
                                        {({ isActive }) => (
                                            <>
                                                <span
                                                    className={[
                                                        "h-2 w-2 rounded-full",
                                                        isActive
                                                            ? "bg-mc-primary shadow-[0_0_8px_rgba(96,165,250,0.7)]"
                                                            : "bg-mc-border",
                                                    ].join(" ")}
                                                />
                                                {item.label}
                                            </>
                                        )}
                                    </NavLink>
                                ) : (
                                    <div
                                        key={item.path}
                                        className="mc-disabled flex items-center gap-3 rounded-mc-md px-3 py-2.5 text-sm font-medium"
                                    >
                                        <span className="h-2 w-2 rounded-full bg-mc-disabled-muted" />
                                        {item.label}
                                        <span className="ml-auto text-[10px] uppercase tracking-wider text-mc-text-disabled">
                                            Soon
                                        </span>
                                    </div>
                                ),
                            )}
                        </nav>

                        <div className="border-t border-mc-divider px-6 py-5">
                            <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-mc-text-muted">
                                <span className="h-2 w-2 rounded-full bg-mc-success shadow-[0_0_8px_rgba(52,211,153,0.65)]" />
                                Atlas Core
                            </div>
                            <p className="mt-2 text-xs text-mc-text-disabled">
                                {release ?? "Release unavailable"}
                            </p>
                        </div>
                    </div>
                </aside>

                <div className="min-w-0">
                    <Outlet />
                </div>
            </div>
        </div>
    );
}
