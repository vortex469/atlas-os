import { describe, expect, it } from "vitest";

import { serviceListeningPortCommand, serviceReachabilityCommand } from "./serviceReachabilityCommand";

describe("serviceListeningPortCommand", () => {
    it("checks the configured HTTP port without exposing URL details", () => {
        expect(serviceListeningPortCommand("http://operator:secret@10.10.60.30:8080/health?token=private"))
            .toBe("ss -ltnp 'sport = :8080'");
    });

    it.each([
        ["http://example.test/", "ss -ltnp 'sport = :80'"],
        ["https://example.test/", "ss -ltnp 'sport = :443'"],
    ])("uses the default port for %s", (address, command) => {
        expect(serviceListeningPortCommand(address)).toBe(command);
    });

    it.each([undefined, null, "", "not a URL", "file:///etc/passwd", "http://example.test:70000/"])(
        "does not produce a command for an invalid or non-HTTP address (%s)",
        value => expect(serviceListeningPortCommand(value)).toBeNull(),
    );
});

describe("serviceReachabilityCommand", () => {
    it("builds a read-only Core-container probe for an HTTP endpoint", () => {
        expect(serviceReachabilityCommand("http://10.10.60.30:8080/"))
            .toBe("docker compose --file compose.production.yaml exec --no-TTY atlas-core python -c 'import httpx; response = httpx.get(\"http://10.10.60.30:8080/\", timeout=3.0, follow_redirects=True); print(response.status_code)'");
    });

    it("omits URL credentials, query values, and fragments", () => {
        const command = serviceReachabilityCommand(
            "https://operator:private@example.test:8443/health?token=secret#private",
        );

        expect(command).toContain('httpx.get("https://example.test:8443/health"');
        expect(command).not.toMatch(/operator|private|secret|token=/);
    });

    it("shell-quotes a URL containing a single quote", () => {
        const command = serviceReachabilityCommand("http://example.test/owner's-health");

        expect(command).toContain("'\"'\"'");
        expect(command).toContain("owner'\"'\"'s-health");
    });

    it.each([undefined, null, "", "not a URL", "file:///etc/passwd"])(
        "does not produce a command for an invalid or non-HTTP address (%s)",
        value => expect(serviceReachabilityCommand(value)).toBeNull(),
    );
});
