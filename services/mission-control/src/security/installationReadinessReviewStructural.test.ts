import { describe, expect, it } from "vitest";

import client from "../api/installationReadinessReview.ts?raw";
import router from "../app/router.tsx?raw";
import candidateContext from "../features/discovery/InstallationCandidateLifecycle.tsx?raw";
import page from "../pages/InstallationReadinessReviewPage.tsx?raw";

describe("v0.34 installation readiness review release boundary", () => {
    it("has exactly one GET client and no mutation, polling, or refresh path", () => {
        expect(client.match(/atlas\.get/g)).toHaveLength(1);
        expect(client).toContain("/installation/candidate-records/");
        expect(client).toContain("/readiness-review");
        expect(client).not.toMatch(/atlas\.(?:post|put|patch|delete)/i);
        expect(client).not.toMatch(/setInterval|setTimeout|(?:poll|refresh|retry|resend)\s*\(/i);
    });

    it("registers only the frozen page and candidate-context navigation", () => {
        expect(router.match(/candidateRecordId\/readiness-review/g)).toHaveLength(1);
        expect(candidateContext.match(/candidate_record_id\)}\/readiness-review/g)).toHaveLength(1);
        expect(router).not.toMatch(/readiness-review\/(?:install|execute|dispatch|retry|resend|deploy|rollback|mutation)/i);
        expect(candidateContext).not.toMatch(/readiness-review[^\n]*(?:button|onClick|post|put|patch|delete)/i);
    });

    it("has no form, effect control, polling, or mutation call", () => {
        expect(page).not.toMatch(/<(?:button|form|input|select|textarea)\b/i);
        expect(page).not.toMatch(/setInterval|setTimeout|useMutation|atlas\.(?:post|put|patch|delete)/i);
        for (const label of [
            "install now", "execute now", "run now", "deploy now", "dispatch now",
            "retry now", "resend now", "send to agent", "start workflow", "roll back now",
        ]) expect(page.toLowerCase()).not.toContain(label);
    });

    it("renders only closed summaries and no sensitive raw data field", () => {
        for (const marker of [
            "provider_payload", "request_body", "response_body", "authorization_header",
            "credential_value", "bearer_token", "command_argv", "stdout", "stderr",
            "internal_path", "endpoint_url", "host_address",
        ]) expect(page).not.toContain(marker);
        expect(page).toContain("evidence_fingerprint");
        expect(page).toContain("audit_evidence");
        expect(page).toContain("mutation_attempted");
    });

    it("states the complete non-authorizing boundary and Home Assistant blocker", () => {
        expect(page).toMatch(/not installation, execution, dispatch, retry or resend, Agent invocation, workflow start, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or permission to mutate anything/i);
        expect(page).toContain("installation_capability_unsupported");
        expect(page).toContain("Installation capability unsupported");
    });
});
