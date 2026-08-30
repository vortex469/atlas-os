import { describe, expect, it } from "vitest";

import client from "../api/executionPermissionGrant.ts?raw";
import router from "../app/router.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import page from "../pages/InstallationReadinessReviewPage.tsx?raw";

describe("v0.35 execution permission evidence presentation boundary", () => {
    it("uses only the exact P3 collection create/list and item get", () => {
        expect(client.match(/atlas\.get/g)).toHaveLength(2);
        expect(client.match(/atlas\.post/g)).toHaveLength(1);
        expect(client).not.toMatch(/atlas\.(?:put|patch|delete)/i);
        expect(client).not.toMatch(/setInterval|setTimeout|poll|refresh/i);
        expect(client).toContain("/execution-permission-grants");
        expect(client).toContain('"X-Atlas-CSRF-Token"');
        expect(client).toContain('"Idempotency-Key"');
    });

    it("adds no grant action route or global navigation", () => {
        expect(router).not.toMatch(/execution-permission-grants/i);
        expect(navigation).not.toMatch(/execution permission|permission grant/i);
        expect(page).not.toMatch(/<(?:form|input|select|textarea)\b/i);
    });

    it("has no polling, sensitive field, or prohibited effect control", () => {
        expect(page).not.toMatch(/setInterval|setTimeout|useMutation/i);
        for (const marker of ["provider_payload", "request_body", "response_body", "credential_value", "bearer_token", "command_argv", "stdout", "stderr", "internal_path", "endpoint_url", "host_address"]) expect(page).not.toContain(marker);
        for (const label of ["install now", "execute now", "run now", "deploy now", "dispatch now", "retry now", "resend now", "send to agent", "start workflow", "roll back now"]) expect(page.toLowerCase()).not.toContain(label);
    });

    it("locks the exact evidence-only confirmation and full authority disclaimer", () => {
        expect(page).toContain("EXECUTION_PERMISSION_CONFIRMATION");
        expect(page).toMatch(/creates durable permission evidence only/i);
        expect(page).toMatch(/not installation, execution, dispatch, retry or resend, Agent invocation, workflow start, worker execution, Docker, Podman, shell or process execution, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or permission to mutate anything/i);
        expect(page).toMatch(/Home Assistant remains non-installable and non-executable/i);
    });
});
