type RefreshIndicatorProps = {
    active: boolean;
};

export function RefreshIndicator({ active }: RefreshIndicatorProps) {
    if (!active) return null;

    return (
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-blue-300" aria-live="polite">
            <span className="h-2 w-2 animate-pulse rounded-full bg-blue-400" />
            Refreshing
        </div>
    );
}
