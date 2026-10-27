import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { InstallationPlan, InstallationPlanBlockerCode, InstallationPlanStatus } from "../../types/installationPlan";
import { InstallationPlanReview } from "./InstallationPlanReview";

import { FINGERPRINT, homeAssistantGoldenPlan } from "../../test/installationPlan.fixture";

function genericPlan(status: InstallationPlanStatus = "missing_deployment_artifact"): InstallationPlan {
    const blockerCode: Record<Exclude<InstallationPlanStatus, "plan_ready_for_review">, InstallationPlanBlockerCode> = {
        conflicted: "provenance_conflict",
        missing_deployment_artifact: "missing_deployment_artifact",
        incompatible: "incompatible_application_environment",
        stale_evidence: "stale_evidence",
        insufficient_information: "missing_prerequisite_fact",
    };
    const blockers = status === "plan_ready_for_review" ? [] : [{ code: blockerCode[status], subject: "home-assistant" }];
    return {
        schema_version: "installation-plan-v1",
        fingerprint: { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: FINGERPRINT },
        application: { item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", display_name: "Home Assistant", release_version: "2026.8.3" },
        status,
        deployment_artifact: { state: status === "missing_deployment_artifact" ? "missing" : "present", kind: "docker-compose", repository_path: "compose/home-assistant.yaml", service: "home-assistant", content_digest: null },
        image: { state: "missing", reference: null, digest: null, release_version: "2026.8.3" },
        accepted_evidence: [{
            evidence_id: "930204abdb4caf6f4cb5da28ffc00c315370933211b5097a7e653e0953af5e11",
            source_class: "registry_attested",
            source_id: "collector:home-assistant-ghcr-cosign",
            subject: "home-assistant",
            claim: "immutable_image_release",
            immutable_identity: "4d60b08f34e168cb5ac825671682cfb9855175fa09fc08450e8bcdc84692d7c3",
            observed_at: null,
            attested_at: "2026-08-21T20:54:36Z",
            freshness_window_seconds: 2592000,
            trust: "accepted",
        }],
        provenance: [{ claim: "deployment-binding", source_class: "deployment_binding", source_id: "home-assistant", immutable_identity: "b".repeat(64), observed_at: null, attested_at: null }],
        compatibility: [{ environment: "item-scoped", result: status === "incompatible" ? "incompatible" : "unknown", reason_code: status === "incompatible" ? "target_free_catalog_incompatible" : "compatibility_fact_missing" }],
        prerequisites: [{ prerequisite_id: "storage", kind: "storage", state: "unknown", description: "Confirm durable storage" }],
        relationships: [{ kind: "integrates_with", item_id: "mqtt", required: false, minimum_version: null, maximum_version: "6.0" }],
        assumptions: [{ assumption_id: "operator-maintenance", kind: "operator", statement: "A maintenance window is available." }],
        blockers,
        risks: [{ code: "compatibility_warning", severity: "high", subject: "storage-layout" }],
        missing_facts: status === "plan_ready_for_review" ? [] : [{ code: "deployment_artifact", subject: "home-assistant" }],
        required_operator_confirmations: [{ code: "confirm_risk", subject: "storage-layout", prompt: "Confirm the storage migration risk." }],
    };
}


describe("InstallationPlanReview", () => {
    it.each<InstallationPlanStatus>([
        "conflicted",
        "missing_deployment_artifact",
        "incompatible",
        "stale_evidence",
        "insufficient_information",
        "plan_ready_for_review",
    ])("renders the closed %s status without execution authority", (status) => {
        render(<InstallationPlanReview plan={genericPlan(status)} isLoading={false} unavailable={false} />);
        const panel = screen.getByRole("heading", { name: "Installation plan review" }).closest("section")!;
        expect(within(panel).getAllByText(status.replaceAll("_", " "), { exact: false }).length).toBeGreaterThan(0);
        expect(within(panel).queryByRole("button")).not.toBeInTheDocument();
        expect(within(panel).queryByRole("link")).not.toBeInTheDocument();
    });

    it("keeps blockers, confirmations, risks, provenance, and fingerprint informational", () => {
        render(<InstallationPlanReview plan={genericPlan()} isLoading={false} unavailable={false} />);
        expect(screen.getByText(FINGERPRINT)).toBeInTheDocument();
        expect(screen.getByText("Integrity linkage only — not approval")).toBeInTheDocument();
        expect(screen.getByText(/1 unresolved blocker; this plan is not executable/i)).toBeInTheDocument();
        expect(screen.getByText(/Confirm the storage migration risk/i)).toBeInTheDocument();
        expect(screen.getByText(/High · Compatibility Warning/i)).toBeInTheDocument();
        expect(screen.getByText(/Claim: deployment-binding · Source class: deployment_binding/i)).toHaveTextContent("Observed at: None · Attested at: None");
        expect(screen.queryByRole("button", { name: /approve|confirm|install|execute|deploy|convert/i })).not.toBeInTheDocument();
    });

    it("renders hostile opaque-looking text as inert text", () => {
        const hostile = genericPlan();
        hostile.required_operator_confirmations[0].prompt = "<img src=x onerror=alert(1)>";
        const { container } = render(<InstallationPlanReview plan={hostile} isLoading={false} unavailable={false} />);
        expect(screen.getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
        expect(container.querySelector("img")).toBeNull();
    });

    it("shows the exact Home Assistant missing-artifact result without action controls", () => {
        render(<InstallationPlanReview plan={homeAssistantGoldenPlan()} isLoading={false} unavailable={false} />);
        expect(screen.getAllByText(/Missing Deployment Artifact/).length).toBeGreaterThan(0);
        expect(screen.getAllByText("2026.8.3", { selector: "dd" })).toHaveLength(2);
        expect(screen.getByText("d5-home-assistant")).toBeInTheDocument();
        expect(screen.getByText("Home Assistant")).toBeInTheDocument();
        expect(screen.getByText("docker-compose")).toBeInTheDocument();
        expect(screen.getByText("compose/home-assistant.yaml")).toBeInTheDocument();
        expect(screen.getAllByText("home-assistant", { selector: "dd" })).toHaveLength(2);
        expect(screen.getAllByText("None", { selector: "dd" })).toHaveLength(3);
        expect(screen.getAllByText("Missing", { selector: "dd" })).toHaveLength(2);
        expect(screen.getByText(/Result: Unknown · Reason code: compatibility_fact_missing/)).toBeInTheDocument();
        expect(screen.getByText(/Source class: registry_attested/)).toHaveTextContent("collector:home-assistant-ghcr-cosign");
        expect(screen.getByText(/Source class: registry_attested/)).toHaveTextContent("Subject: home-assistant");
        expect(screen.getByText(/Source class: registry_attested/)).toHaveTextContent("Observed at: None");
        expect(screen.getByText(/Source class: registry_attested/)).toHaveTextContent("2026-08-21T20:54:36Z");
        expect(screen.getByText(/Source class: registry_attested/)).toHaveTextContent("Freshness window seconds: 2592000 · Trust: accepted");
        expect(screen.getByText(/Prerequisite ID: 833c8f/)).toHaveTextContent("Kind: network · State: unknown · Description: Requires port 8123/tcp");
        expect(screen.getByText(/Prerequisite ID: 9d3cb7/)).toHaveTextContent("Kind: platform · State: unknown · Description: Requires capability container-orchestration.");
        expect(screen.getByText(/Item: mqtt/)).toHaveTextContent("Minimum version: None · Maximum version: None");
        expect(screen.getByText(/Item: postgresql/)).toHaveTextContent("Required: No");
        expect(screen.getByText(/Assumption ID: 091e943/)).toHaveTextContent("Target environment must be checked");
        expect(screen.getByText(/Assumption ID: 833cc1/)).toHaveTextContent("Target environment must be checked");
        expect(screen.getByText(/Claim: catalog_entry/)).toHaveTextContent("Source class: curated_catalog");
        expect(screen.getByText(/Claim: freshness/)).toHaveTextContent("Observed at: 2026-08-25T00:00:00Z");
        expect(screen.getByText(/Claim: immutable_image_release · Source class: image_release_evidence/)).toBeInTheDocument();
        expect(screen.getByText(/9 unresolved blockers; this plan is not executable/i)).toBeInTheDocument();
        expect(screen.getByText(/Missing Immutable Image Identity/)).toBeInTheDocument();
        expect(screen.getByText(/Unknown Compatibility/)).toBeInTheDocument();
        for (const code of ["Deployment Artifact", "Immutable Image Identity", "Prerequisite Fact", "Compatibility Fact"]) {
            expect(screen.getAllByText(new RegExp(code)).length).toBeGreaterThan(0);
        }
        expect(screen.getByText("No risks reported.")).toBeInTheDocument();
        expect(screen.getAllByText(/Review the informational assumption/)).toHaveLength(2);
        expect(screen.getAllByText(/Review the informational prerequisite/)).toHaveLength(2);
        expect(screen.getByRole("heading", { name: "Blockers" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Missing facts" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Required operator confirmations" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Risks" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Provenance" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Accepted evidence" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Relationships" })).toBeInTheDocument();
        expect(screen.getByText(FINGERPRINT)).toBeInTheDocument();
        expect(screen.getByText("sha256")).toBeInTheDocument();
        expect(screen.getByText("atlas-jcs-nfc-v1")).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
