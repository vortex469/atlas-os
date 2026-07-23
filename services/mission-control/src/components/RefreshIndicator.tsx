type RefreshIndicatorProps = {
    active: boolean;
};

export function RefreshIndicator({
    active,
}: RefreshIndicatorProps) {
    return (
        <div
            className={[
                "flex items-center gap-2 text-xs uppercase tracking-wider",
                active ? "text-blue-300" : "text-slate-500",
            ].join(" ")}
            aria-live="polite"
        >
            <span
                className={[
                    "h-2 w-2 rounded-full",
                    active
                        ? "animate-pulse bg-blue-400"
                        : "bg-slate-600",
                ].join(" ")}
            />

            {active ? "Refreshing" : "Live"}
        </div>
    );
}
