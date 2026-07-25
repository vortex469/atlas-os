import { NavLink, Outlet } from "react-router-dom";

type NavigationItem = {
    label: string;
    path: string;
    enabled: boolean;
};

const navigationItems: NavigationItem[] = [
    { label: "Mission Control", path: "/", enabled: true },
    { label: "Operations", path: "/operations", enabled: true },
    { label: "Forge", path: "/forge", enabled: true },
    { label: "Knowledge", path: "/knowledge", enabled: false },
    { label: "Developer", path: "/developer", enabled: false },
    { label: "Settings", path: "/settings", enabled: false },
];

export function MainLayout() {
    return (
        <div className="min-h-screen bg-slate-950 text-slate-100">
            <div className="grid min-h-screen lg:grid-cols-[15rem_1fr]">
                <aside className="border-r border-slate-800 bg-slate-900">
                    <div className="flex min-h-screen flex-col">
                        <div className="border-b border-slate-800 px-6 py-6">
                            <p className="text-xl font-bold tracking-[0.25em]">
                                ATLAS
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
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
                                                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
                                                isActive
                                                    ? "bg-blue-500/10 text-blue-300"
                                                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-100",
                                            ].join(" ")
                                        }
                                    >
                                        {({ isActive }) => (
                                            <>
                                                <span
                                                    className={[
                                                        "h-2 w-2 rounded-full",
                                                        isActive
                                                            ? "bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.7)]"
                                                            : "bg-slate-700",
                                                    ].join(" ")}
                                                />
                                                {item.label}
                                            </>
                                        )}
                                    </NavLink>
                                ) : (
                                    <div
                                        key={item.path}
                                        className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600"
                                    >
                                        <span className="h-2 w-2 rounded-full bg-slate-800" />
                                        {item.label}
                                        <span className="ml-auto text-[10px] uppercase tracking-wider text-slate-700">
                                            Soon
                                        </span>
                                    </div>
                                ),
                            )}
                        </nav>

                        <div className="border-t border-slate-800 px-6 py-5">
                            <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-500">
                                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.65)]" />
                                Atlas Core
                            </div>
                            <p className="mt-2 text-xs text-slate-600">
                                Foundry 0.1
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
