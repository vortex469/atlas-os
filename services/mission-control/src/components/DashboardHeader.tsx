type DashboardHeaderProps = {
    lastUpdated: Date | null;
};

export function DashboardHeader({
    lastUpdated,
}: DashboardHeaderProps) {
    return (
        <header className="border-b border-slate-800 bg-slate-900">
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-8">
                <div>
                    <h1 className="text-xl font-bold tracking-[0.2em] text-slate-100">
                        ATLAS
                    </h1>

                    <p className="text-xs text-slate-400">
                        Mission Control
                    </p>
                </div>

                <div className="text-right">
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                        Last Updated
                    </p>

                    <p className="mt-1 text-sm text-slate-300">
                        {lastUpdated
                            ? lastUpdated.toLocaleTimeString()
                            : "Connecting..."}
                    </p>
                </div>
            </div>
        </header>
    );
}