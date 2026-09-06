type StatusBadgeProps = {
    status: string;
};

type StatusStyle = {
    variant: string;
};

const statusStyles: Record<string, StatusStyle> = {
    healthy: { variant: "mc-status-success" },
    online: { variant: "mc-status-success" },
    success: { variant: "mc-status-success" },
    degraded: { variant: "mc-status-warning" },
    warning: { variant: "mc-status-warning" },
    critical: { variant: "mc-status-error" },
    error: { variant: "mc-status-error" },
    failed: { variant: "mc-status-error" },
    offline: { variant: "mc-status-error" },
    running: { variant: "mc-status-info" },
    pending: { variant: "mc-status-info" },
    "in-progress": { variant: "mc-status-info" },
    unavailable: { variant: "mc-status-disabled" },
    disabled: { variant: "mc-status-disabled" },
    unknown: { variant: "mc-status-neutral" },
};

export function StatusBadge({ status }: StatusBadgeProps) {
    const normalizedStatus = status.trim().toLowerCase();

    const style =
        statusStyles[normalizedStatus] ??
        statusStyles.unknown;

    return (
        <span
            className={[
                "mc-status-badge",
                style.variant,
            ].join(" ")}
            data-mc-status={style.variant.replace("mc-status-", "")}
        >
            <span
                className="mc-status-dot"
                aria-hidden="true"
            />

            {status}
        </span>
    );
}
