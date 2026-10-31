/** Show running and stopped service containers, networks, and published ports. */
export const serviceContainerCheckCommand = "docker ps --all --format 'table {{.Names}}\\t{{.Status}}\\t{{.Networks}}\\t{{.Ports}}'";

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
