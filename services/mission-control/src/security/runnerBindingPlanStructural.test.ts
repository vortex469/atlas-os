import { describe, expect, it } from "vitest";

import client from "../api/runnerBindingPlan.ts?raw";
import router from "../app/router.tsx?raw";
import component from "../features/installation/RunnerBindingPlans.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

const productionModules = import.meta.glob(
    ["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"],
    { eager: true, query: "?raw", import: "default" },
) as Record<string, string>;

describe("v0.37 runner binding plan presentation boundary", () => {
    it("uses only the exact guarded P3 create/list/get client", () => {
        expect(client.match(/atlas\.get/g)).toHaveLength(2);
        expect(client.match(/atlas\.post/g)).toHaveLength(1);
        expect(client).not.toMatch(/atlas\.(?:put|patch|delete)/i);
        expect(client).not.toMatch(/setInterval|setTimeout|poll|refresh/i);
        expect(client).toContain("/runner-binding-plans");
        expect(client).toContain('"X-Atlas-CSRF-Token"');
        expect(client).toContain('"Idempotency-Key"');
    });
    it("adds no standalone route, navigation, polling, form, or editable runner selection", () => {
        expect(router).not.toMatch(/runner-binding-plans|RunnerBindingPlan/i);
        expect(navigation).not.toMatch(/runner binding plan|binding-planned/i);
        expect(component).not.toMatch(/<(?:form|input|select|textarea)\b/i);
        expect(component).not.toMatch(/setInterval|setTimeout|useMutation|poll/i);
        expect(component).not.toMatch(/discoverRunner|runnerDiscovery|\/runners\b/i);
    });
    it("contains no sensitive rendering or prohibited effect control", () => {
        for (const marker of ["provider_payload", "credential_value", "bearer_token", "command_argv", "stdout", "stderr", "internal_path", "endpoint_url", "host_address", "mount_source"]) expect(component).not.toContain(marker);
        for (const label of ["bind runner", "run now", "start execution", "execute now", "install now", "deploy now", "dispatch now", "retry now", "resend now", "send to agent", "start workflow", "roll back now"]) expect(component.toLowerCase()).not.toContain(label);
    });
    it("locks evidence-only copy, blockers, limits, and Home Assistant closure", () => {
        expect(component).toMatch(/records a runner binding plan only/i);
        expect(component).toMatch(/does not bind or contact a runner and does not authorize or start installation or execution/i);
        expect(component).toContain("runner_not_bound");
        expect(component).toContain("execution_start_boundary_not_defined");
        expect(client).toContain("atlas-installation-confined-v1");
        expect(component).toMatch(/Home Assistant remains blocked, non-installable, non-executable/i);
    });
    it("has no consumer outside the exact client, admission context, types, and presentation", () => {
        const consumers = Object.entries(productionModules).filter(([, source]) => /runner-binding-plans|RunnerBindingPlan/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/runnerBindingPlan.ts",
            "../features/installation/InstallationExecutionAdmissions.tsx",
            "../features/installation/RunnerBindingPlans.tsx",
            "../types/runnerBindingPlan.ts",
        ]);
    });
});
