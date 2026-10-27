// @vitest-environment node
import { createServer as createHttpServer } from "node:http";
import { createServer as createTcpServer } from "node:net";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createServer } from "vite";
import type { ViteDevServer } from "vite";

async function availablePort(): Promise<number> {
    const probe = createTcpServer();
    await new Promise<void>((resolve, reject) => {
        probe.once("error", reject);
        probe.listen(0, "127.0.0.1", resolve);
    });
    const address = probe.address();
    if (!address || typeof address === "string") throw new Error("Port probe did not bind");
    const port = address.port;
    await new Promise<void>((resolve, reject) => {
        probe.close((error) => error ? reject(error) : resolve());
    });
    return port;
}

// Exercise the actual development proxy against an isolated HTTP stub.
// No Atlas service is started or contacted, and every request is a GET.
describe("development API proxies", () => {
    const backend = createHttpServer((request, response) => {
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify({ path: request.url, headers: request.headers }));
    });
    let vite: ViteDevServer;
    let base: string;
    beforeAll(async () => {
        await new Promise<void>((resolve, reject) => {
            backend.once("error", reject);
            backend.listen(0, "127.0.0.1", () => resolve());
        });
        const address = backend.address();
        if (!address || typeof address === "string") throw new Error("Stub did not bind");
        const target = `http://127.0.0.1:${address.port}`;
        const port = await availablePort();
        vite = await createServer({
            root: fileURLToPath(new URL("../../", import.meta.url)),
            configFile: fileURLToPath(new URL("../../vite.config.ts", import.meta.url)),
            logLevel: "silent",
            optimizeDeps: { noDiscovery: true, include: [] },
            server: { host: "127.0.0.1", port, strictPort: true,
                proxy: { "/api/v1": { target }, "/agent-api": { target } } },
        });
        await vite.listen();
        const listening = vite.httpServer?.address();
        if (!listening || typeof listening === "string") throw new Error("Vite did not bind");
        base = `http://127.0.0.1:${listening.port}`;
    });
    afterAll(async () => {
        await vite?.close();
        backend.closeAllConnections();
        await new Promise<void>((resolve) => backend.close(() => resolve()));
    });

    it.each([
        ["/agent-api/api/v1/agent/workflows?limit=2", "/api/v1/agent/workflows?limit=2"],
        ["/api/v1/health?format=brief", "/api/v1/health?format=brief"],
    ])("forwards %s as JSON with backend-owned identity", async (path, expected) => {
        const response = await fetch(`${base}${path}`, { headers: {
            "X-Atlas-Operator": "spoofed", "X-Auth-User": "spoofed", "X-User": "spoofed", "Remote-User": "spoofed",
            Cookie: "fixture-session=example", "X-Atlas-CSRF-Token": "fixture-only-csrf",
            Origin: base,
        } });
        expect(response.status).toBe(200);
        expect(response.headers.get("content-type")).toContain("application/json");
        const result = await response.json();
        expect(result.path).toBe(expected);
        for (const header of ["x-atlas-operator", "x-auth-user", "x-user", "remote-user"]) expect(result.headers[header]).toBeUndefined();
        expect(result.headers.cookie).toBe("fixture-session=example");
        expect(result.headers["x-atlas-csrf-token"]).toBe("fixture-only-csrf");
        expect(result.headers.origin).toBe(base);
    });
});
