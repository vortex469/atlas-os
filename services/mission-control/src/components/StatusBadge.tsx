type StatusBadgeProps = {
    status: string;
};

type StatusStyle = {
    badge: string;
    dot: string;
};

const statusStyles: Record<string, StatusStyle> = {
    healthy: {
        badge:
            "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        dot: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.75)]",
    },
    online: {
        badge:
            "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        dot: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.75)]",
    },
    degraded: {
        badge:
            "border-amber-500/30 bg-amber-500/10 text-amber-400",
        dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.65)]",
    },
    warning: {
        badge:
            "border-amber-500/30 bg-amber-500/10 text-amber-400",
        dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.65)]",
    },
    critical: {
        badge:
            "border-red-500/30 bg-red-500/10 text-red-400",
        dot: "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.75)]",
    },
    offline: {
        badge:
            "border-red-500/30 bg-red-500/10 text-red-400",
        dot: "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.75)]",
    },
    unknown: {
        badge:
            "border-slate-600 bg-slate-800 text-slate-300",
        dot: "bg-slate-500",
    },
};

export function StatusBadge({ status }: StatusBadgeProps) {
    const normalizedStatus = status.trim().toLowerCase();

    const style =
        statusStyles[normalizedStatus] ??
        statusStyles.unknown;

    return (
        <span
            className={[
                "inline-flex items-center gap-2 rounded-full border",
                "px-3 py-1 text-xs font-semibold uppercase tracking-wider",
                style.badge,
            ].join(" ")}
        >
            <span
                className={`h-1.5 w-1.5 rounded-full ${style.dot}`}
                aria-hidden="true"
            />

            {status}
        </span>
    );
}
