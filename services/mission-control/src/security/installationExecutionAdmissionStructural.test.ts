import { describe, expect, it } from "vitest";

import client from "../api/installationExecutionAdmission.ts?raw";
import router from "../app/router.tsx?raw";
import component from "../features/installation/InstallationExecutionAdmissions.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

describe("v0.36 installation execution admission presentation boundary", () => {
    it("uses only the exact guarded P3 create/list/get client", () => {
        expect(client.match(/atlas\.get/g)).toHaveLength(2);
        expect(client.match(/atlas\.post/g)).toHaveLength(1);
        expect(client).not.toMatch(/atlas\.(?:put|patch|delete)/i);
        expect(client).not.toMatch(/setInterval|setTimeout|poll|refresh/i);
        expect(client).toContain("/execution-admissions");
        expect(client).toContain('"X-Atlas-CSRF-Token"');
        expect(client).toContain('"Idempotency-Key"');
    });

    it("adds no action route, navigation, polling, or form surface", () => {
        expect(router).not.toMatch(/execution-admissions/i);
        expect(navigation).not.toMatch(/execution admission|admission evidence/i);
        expect(component).not.toMatch(/<(?:form|input|select|textarea)\b/i);
        expect(component).not.toMatch(/setInterval|setTimeout|useMutation|poll/i);
    });

    it("contains no sensitive rendering or prohibited effect control", () => {
        for (const marker of ["provider_payload", "request_body", "response_body", "credential_value", "bearer_token", "command_argv", "stdout", "stderr", "internal_path", "endpoint_url", "host_address"]) expect(component).not.toContain(marker);
        for (const label of ["install now", "execute now", "run now", "start execution", "deploy now", "dispatch now", "retry now", "resend now", "send to agent", "start workflow", "roll back now", "bind runner"]) expect(component.toLowerCase()).not.toContain(label);
    });

    it("locks evidence-only copy, fixed blockers, and Home Assistant closure", () => {
        expect(component).toMatch(/preserves a non-executing admission evidence record only/i);
        expect(component).toMatch(/not runner binding, execution start, installation, dispatch, retry or resend, Agent invocation, workflow or worker start/i);
        expect(component).toContain("runner_binding_not_defined");
        expect(component).toContain("execution_start_boundary_not_defined");
        expect(component).toMatch(/Home Assistant remains blocked, non-installable, and non-executable/i);
    });
});
