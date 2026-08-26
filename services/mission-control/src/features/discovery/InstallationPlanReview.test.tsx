import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { InstallationPlan, InstallationPlanBlockerCode, InstallationPlanStatus } from "../../types/installationPlan";
import { InstallationPlanReview } from "./InstallationPlanReview";

const FINGERPRINT = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a";

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

function homeAssistantGoldenPlan(): InstallationPlan {
    return {
        schema_version: "installation-plan-v1",
        fingerprint: { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: FINGERPRINT },
        application: { item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", display_name: "Home Assistant", release_version: "2026.8.3" },
        status: "missing_deployment_artifact",
        deployment_artifact: { state: "missing", kind: "docker-compose", repository_path: "compose/home-assistant.yaml", service: "home-assistant", content_digest: null },
        image: { state: "missing", reference: null, digest: null, release_version: "2026.8.3" },
        accepted_evidence: [{
            evidence_id: "930204abdb4caf6f4cb5da28ffc00c315370933211b5097a7e653e0953af5e11",
            source_class: "registry_attested", source_id: "collector:home-assistant-ghcr-cosign",
            subject: "home-assistant", claim: "immutable_image_release",
            immutable_identity: "4d60b08f34e168cb5ac825671682cfb9855175fa09fc08450e8bcdc84692d7c3",
            observed_at: null, attested_at: "2026-08-21T20:54:36Z", freshness_window_seconds: 2592000, trust: "accepted",
        }],
        provenance: [
            { claim: "catalog_entry", source_class: "curated_catalog", source_id: "atlas-curated-discovery-catalog", immutable_identity: "742ee0e9b322c34f36c8ce6e2ca17370c548b38572ae69c049c91abc84aed207", observed_at: null, attested_at: "2026-08-21T20:54:36Z" },
            { claim: "compatibility", source_class: "compatibility_evaluation", source_id: "compatibility-projector", immutable_identity: "ed4cd909345d8fb4e1575b048e5948c76a8b2ac557a5a3347a38d7b415d396f3", observed_at: null, attested_at: null },
            { claim: "deployment_artifact", source_class: "repository_observation", source_id: "repository-observer", immutable_identity: "54987176debc1cd6aa7591ccf1cb8f68d4c667ad89ccc36bab7dc8701683fdbe", observed_at: null, attested_at: null },
            { claim: "deployment_binding", source_class: "deployment_binding", source_id: "deployment-binding", immutable_identity: "2836042a3b43c570864ae42f698068b74f7a115fe1d61793512898e5ed1b910d", observed_at: null, attested_at: null },
            { claim: "freshness", source_class: "policy_evaluation", source_id: "freshness-policy", immutable_identity: "d3c5722715450b6510ff69364f5023b88ed6e0d904fe4c28131af03f76b66aa0", observed_at: "2026-08-25T00:00:00Z", attested_at: null },
            { claim: "immutable_image_release", source_class: "image_release_evidence", source_id: "collector:home-assistant-ghcr-cosign", immutable_identity: "4d60b08f34e168cb5ac825671682cfb9855175fa09fc08450e8bcdc84692d7c3", observed_at: null, attested_at: "2026-08-21T20:54:36Z" },
            { claim: "prerequisite", source_class: "prerequisite_source", source_id: "prerequisite-projector", immutable_identity: "c830b8d625908c8bd5ed864a0ef8c54b5064ef4b9eb0935d2189adab024dd05e", observed_at: null, attested_at: null },
            { claim: "prerequisite", source_class: "prerequisite_source", source_id: "prerequisite-projector", immutable_identity: "eb2110c10d2c108adb32f5c4e72e4203a62755ef235075bef029c4e19f2063ce", observed_at: null, attested_at: null },
        ],
        compatibility: [{ environment: "item-scoped", result: "unknown", reason_code: "compatibility_fact_missing" }],
        prerequisites: [
            { prerequisite_id: "833c8f05ff5931f984ba64333f4414d2d509b6e57c315889a1b045828982e305", kind: "network", state: "unknown", description: "Requires port 8123/tcp in the inbound direction (required: false)." },
            { prerequisite_id: "9d3cb7ff423f1d8fb59e694984a38b6952216aa66409abd2548738fe81043a75", kind: "platform", state: "unknown", description: "Requires capability container-orchestration." },
        ],
        relationships: [
            { kind: "integrates_with", item_id: "mqtt", required: false, minimum_version: null, maximum_version: null },
            { kind: "integrates_with", item_id: "postgresql", required: false, minimum_version: null, maximum_version: null },
        ],
        assumptions: [
            { assumption_id: "091e943ab2a85b603e2eedcf34b2d4c7b8d21a1a33b35950baaadfa8050b9b50", kind: "environment", statement: "Target environment must be checked for prerequisite 9d3cb7ff423f1d8fb59e694984a38b6952216aa66409abd2548738fe81043a75." },
            { assumption_id: "833cc1d5b40d94c3b1239947bd77f192d494ab199edc3c7642bead9f8af68e83", kind: "environment", statement: "Target environment must be checked for prerequisite 833c8f05ff5931f984ba64333f4414d2d509b6e57c315889a1b045828982e305." },
        ],
        blockers: [
            { code: "missing_deployment_artifact", subject: "home-assistant" }, { code: "missing_immutable_image_identity", subject: "home-assistant" }, { code: "unknown_compatibility", subject: "home-assistant" },
            { code: "missing_prerequisite_fact", subject: "833c8f05ff5931f984ba64333f4414d2d509b6e57c315889a1b045828982e305" }, { code: "missing_prerequisite_fact", subject: "9d3cb7ff423f1d8fb59e694984a38b6952216aa66409abd2548738fe81043a75" },
            { code: "required_operator_confirmation", subject: "091e943ab2a85b603e2eedcf34b2d4c7b8d21a1a33b35950baaadfa8050b9b50" }, { code: "required_operator_confirmation", subject: "833c8f05ff5931f984ba64333f4414d2d509b6e57c315889a1b045828982e305" }, { code: "required_operator_confirmation", subject: "833cc1d5b40d94c3b1239947bd77f192d494ab199edc3c7642bead9f8af68e83" }, { code: "required_operator_confirmation", subject: "9d3cb7ff423f1d8fb59e694984a38b6952216aa66409abd2548738fe81043a75" },
        ],
        risks: [],
        missing_facts: [
            { code: "deployment_artifact", subject: "home-assistant" }, { code: "immutable_image_identity", subject: "home-assistant" },
            { code: "prerequisite_fact", subject: "833c8f05ff5931f984ba64333f4414d2d509b6e57c315889a1b045828982e305" }, { code: "prerequisite_fact", subject: "9d3cb7ff423f1d8fb59e694984a38b6952216aa66409abd2548738fe81043a75" }, { code: "compatibility_fact", subject: "home-assistant" },
        ],
        required_operator_confirmations: [
            { code: "accept_assumption", subject: "091e943ab2a85b603e2eedcf34b2d4c7b8d21a1a33b35950baaadfa8050b9b50", prompt: "Review the informational assumption 091e943ab2a85b603e2eedcf34b2d4c7b8d21a1a33b35950baaadfa8050b9b50; this does not approve or authorize any action." },
            { code: "accept_assumption", subject: "833cc1d5b40d94c3b1239947bd77f192d494ab199edc3c7642bead9f8af68e83", prompt: "Review the informational assumption 833cc1d5b40d94c3b1239947bd77f192d494ab199edc3c7642bead9f8af68e83; this does not approve or authorize any action." },
            { code: "confirm_prerequisite", subject: "833c8f05ff5931f984ba64333f4414d2d509b6e57c315889a1b045828982e305", prompt: "Review the informational prerequisite 833c8f05ff5931f984ba64333f4414d2d509b6e57c315889a1b045828982e305; this does not approve or authorize any action." },
            { code: "confirm_prerequisite", subject: "9d3cb7ff423f1d8fb59e694984a38b6952216aa66409abd2548738fe81043a75", prompt: "Review the informational prerequisite 9d3cb7ff423f1d8fb59e694984a38b6952216aa66409abd2548738fe81043a75; this does not approve or authorize any action." },
        ],
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
