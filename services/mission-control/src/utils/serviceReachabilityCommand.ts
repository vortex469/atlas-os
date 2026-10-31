/** Show running and stopped service containers, networks, and published ports. */
export const serviceContainerCheckCommand = "docker ps --all --format 'table {{.Names}}\\t{{.Status}}\\t{{.Networks}}\\t{{.Ports}}'";

/** Show the checked address without exposing credentials or query values. */
export function formatServiceCheckAddress(value: unknown): string | null {
    if (typeof value !== "string" || !value.trim()) return null;

    try {
        const url = new URL(value);
        if (url.protocol !== "http:" && url.protocol !== "https:") return null;
        return `${url.protocol}//${url.host}${url.pathname}${url.search ? "?…" : ""}`;
    } catch {
        return null;
    }
}

/** Show whether a Linux host is listening on the port Atlas checks. */
export function serviceListeningPortCommand(value: unknown): string | null {
    if (typeof value !== "string" || !value.trim()) return null;

    try {
        const url = new URL(value);
        if (url.protocol !== "http:" && url.protocol !== "https:") return null;
        const port = url.port || (url.protocol === "https:" ? "443" : "80");
        if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) return null;
        return `ss -ltnp 'sport = :${port}'`;
    } catch {
        return null;
    }
}

/**
 * Build a read-only HTTP probe that follows Atlas Core's network path.
 * Credentials and query values are excluded so the command is safe to render.
 */
export function serviceReachabilityCommand(value: unknown): string | null {
    if (typeof value !== "string" || !value.trim()) return null;

    try {
        const url = new URL(value);
        if (url.protocol !== "http:" && url.protocol !== "https:") return null;
        url.username = "";
        url.password = "";
        url.search = "";
        url.hash = "";

        const python = `import httpx; response = httpx.get(${JSON.stringify(url.toString())}, timeout=3.0, follow_redirects=True); print(response.status_code)`;
        const shellQuotedPython = `'${python.replaceAll("'", "'\"'\"'")}'`;
        return `docker compose --file compose.production.yaml exec --no-TTY atlas-core python -c ${shellQuotedPython}`;
    } catch {
        return null;
    }
}
