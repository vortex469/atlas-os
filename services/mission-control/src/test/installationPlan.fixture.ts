import type { InstallationPlan } from "../types/installationPlan";

export const FINGERPRINT = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a";

export function homeAssistantGoldenPlan(): InstallationPlan {
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
