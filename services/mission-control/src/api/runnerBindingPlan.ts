import { atlas } from "./atlas";
import { isInstallationExecutionAdmissionLinkage } from "./installationExecutionAdmission";
import type { FingerprintV1 } from "../types/installationReadinessReview";
import type { RunnerBindingPlanCollectionV1, RunnerBindingPlanCreateV1, RunnerBindingPlanResultV1 } from "../types/runnerBindingPlan";

const FP = ["algorithm", "canonicalization", "value"];
const LIMITS = ["schema", "sandbox", "resources", "network", "filesystem", "limits_fingerprint"];
const SANDBOX = ["profile", "privileged", "privilege_escalation", "host_pid_namespace", "host_ipc_namespace", "host_network_namespace", "host_devices", "capabilities_drop_all", "seccomp_required", "apparmor_required"];
const RESOURCES = ["cpu_millis_max", "memory_bytes_max", "pids_max", "wall_time_seconds_max", "output_bytes_max"];
const NETWORK = ["mode", "ingress_allowed", "egress_allowed", "dns_allowed", "image_pull_allowed", "allowed_endpoint_fingerprints"];
const FILESYSTEM = ["root_filesystem_read_only", "host_mounts_allowed", "repository_mount_allowed", "guest_mount_allowed", "internal_path_disclosure_allowed", "ephemeral_workspace_allowed", "ephemeral_workspace_bytes_max", "writable_scope"];
const REFERENCE = ["schema", "runner_reference_id", "owner_operator_id", "runner_kind", "trust_domain", "scope", "eligibility", "identity_fingerprint", "capability_profile_fingerprint", "limits", "valid_from", "valid_until", "reference_fingerprint", "registered", "available", "contacted", "reserved", "invocation_allowed"];
const LINKAGE = ["schema", "operator_id", "candidate_record_id", "execution_admission_linkage", "v020_v035_chain_fingerprint", "readiness_review_fingerprint", "permission_grant_fingerprint", "execution_admission_id", "execution_admission_fingerprint", "execution_admission_status_fingerprint", "runner_reference_id", "runner_reference_fingerprint", "runner_identity_fingerprint", "runner_capability_profile_fingerprint", "limits_fingerprint", "linkage_fingerprint"];
const NO_AUTHORITY = ["evidence_only", "runner_registered", "runner_contacted", "runner_reserved", "runner_bound", "runner_binding_allowed", "execution_start_allowed", "execution_authorized", "installation_allowed", "dispatch_allowed", "retry_allowed", "resend_allowed", "agent_invocation_allowed", "worker_allowed", "workflow_allowed", "docker_allowed", "podman_allowed", "shell_allowed", "process_allowed", "provider_mutation_allowed", "repository_mutation_allowed", "in_guest_mutation_allowed", "deployment_allowed", "rollback_allowed", "replay_allowed"];
const PLAN = ["schema", "plan_id", "operator_id", "candidate_record_id", "recorded_at", "valid_until", "record_state", "lifecycle", "eligibility", "blockers", "linkage", "runner_reference", "limits", "idempotency_key_fingerprint", "request_fingerprint", "plan_fingerprint", ...NO_AUTHORITY];
const STATUS = ["schema", "plan_id", "observed_at", "lifecycle", "eligibility", "blockers", "status_fingerprint", "evidence_only", "runner_bound", "execution_authorized", "replay_allowed"];
const AUDIT_FALSE = ["runner_contact_attempted", "runner_binding_attempted", "worker_start_attempted", "execution_start_attempted", "dispatch_attempted", "agent_invocation_attempted", "workflow_start_attempted", "process_execution_attempted", "mutation_attempted", "effect_attempted", "replay_attempted"];
const AUDIT = ["schema", "event", "outcome", "operator_fingerprint", "candidate_record_fingerprint", "plan_fingerprint", "correlation_fingerprint", "occurred_at", "audit_fingerprint", "evidence_only", ...AUDIT_FALSE];
const ERROR = ["schema", "error_code", "message", "correlation_fingerprint", "retryable", "redacted", "evidence_only", "runner_binding_allowed", "execution_authorized", "mutation_allowed", "replay_allowed"];
const RESULT_FALSE = ["runner_registration_allowed", "runner_contact_allowed", "runner_reservation_allowed", "runner_binding_allowed", "runner_bound", "execution_start_allowed", "execution_authorized", "installation_allowed", "dispatch_allowed", "agent_invocation_allowed", "worker_allowed", "workflow_allowed", "mutation_allowed", "deployment_allowed", "rollback_allowed", "retry_allowed", "replay_allowed"];
const RESULT = ["schema", "disposition", "plan", "status", "audit_evidence", "error", "evidence_only", ...RESULT_FALSE];
const COLLECTION = ["schema", "plans", "evidence_only", "execution_authorized", "mutation_allowed"];
const HEX = /^[a-f0-9]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function obj(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: string[]) { return Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key)); }
function fp(value: unknown): value is FingerprintV1 { return obj(value) && exact(value, FP) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && typeof value.value === "string" && HEX.test(value.value); }
function instant(value: unknown) { return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value) && Number.isFinite(Date.parse(value)); }
function falseFields(value: Record<string, unknown>, fields: string[]) { return fields.every((key) => value[key] === false); }
function fixedBlockers(value: unknown) { return Array.isArray(value) && value.length === 2 && value[0] === "runner_not_bound" && value[1] === "execution_start_boundary_not_defined"; }

export function isRunnerBindingLimits(value: unknown) {
    if (!obj(value) || !exact(value, LIMITS) || value.schema !== "runner-binding-limits-v1" || !fp(value.limits_fingerprint)) return false;
    const sandbox = value.sandbox; const resources = value.resources; const network = value.network; const filesystem = value.filesystem;
    return obj(sandbox) && exact(sandbox, SANDBOX) && sandbox.profile === "atlas-installation-confined-v1" && sandbox.privileged === false && sandbox.privilege_escalation === false && sandbox.host_pid_namespace === false && sandbox.host_ipc_namespace === false && sandbox.host_network_namespace === false && sandbox.host_devices === false && sandbox.capabilities_drop_all === true && sandbox.seccomp_required === true && sandbox.apparmor_required === true
        && obj(resources) && exact(resources, RESOURCES) && resources.cpu_millis_max === 1000 && resources.memory_bytes_max === 536870912 && resources.pids_max === 64 && resources.wall_time_seconds_max === 900 && resources.output_bytes_max === 1048576
        && obj(network) && exact(network, NETWORK) && network.mode === "none" && network.ingress_allowed === false && network.egress_allowed === false && network.dns_allowed === false && network.image_pull_allowed === false && Array.isArray(network.allowed_endpoint_fingerprints) && network.allowed_endpoint_fingerprints.length === 0
        && obj(filesystem) && exact(filesystem, FILESYSTEM) && filesystem.root_filesystem_read_only === true && filesystem.host_mounts_allowed === false && filesystem.repository_mount_allowed === false && filesystem.guest_mount_allowed === false && filesystem.internal_path_disclosure_allowed === false && filesystem.ephemeral_workspace_allowed === true && filesystem.ephemeral_workspace_bytes_max === 268435456 && filesystem.writable_scope === "ephemeral_workspace_only";
}

function reference(value: unknown) {
    return obj(value) && exact(value, REFERENCE) && value.schema === "installation-runner-reference-v1" && typeof value.runner_reference_id === "string" && UUID.test(value.runner_reference_id) && typeof value.owner_operator_id === "string" && value.runner_kind === "isolated_installation_runner" && value.trust_domain === "atlas-installation" && value.scope === "installation_runner_binding_plan_only" && value.eligibility === "eligible_for_binding_plan_only" && fp(value.identity_fingerprint) && fp(value.capability_profile_fingerprint) && isRunnerBindingLimits(value.limits) && instant(value.valid_from) && instant(value.valid_until) && fp(value.reference_fingerprint) && falseFields(value, ["registered", "available", "contacted", "reserved", "invocation_allowed"]);
}

export function isRunnerBindingPlanLinkage(value: unknown) {
    if (!obj(value) || !exact(value, LINKAGE) || value.schema !== "runner-binding-plan-linkage-v1" || typeof value.operator_id !== "string" || typeof value.candidate_record_id !== "string" || !UUID.test(value.candidate_record_id) || !isInstallationExecutionAdmissionLinkage(value.execution_admission_linkage)) return false;
    return typeof value.execution_admission_id === "string" && UUID.test(value.execution_admission_id) && typeof value.runner_reference_id === "string" && UUID.test(value.runner_reference_id) && ["v020_v035_chain_fingerprint", "readiness_review_fingerprint", "permission_grant_fingerprint", "execution_admission_fingerprint", "execution_admission_status_fingerprint", "runner_reference_fingerprint", "runner_identity_fingerprint", "runner_capability_profile_fingerprint", "limits_fingerprint", "linkage_fingerprint"].every((key) => fp(value[key]));
}

function plan(value: unknown) {
    if (!obj(value) || !exact(value, PLAN) || value.schema !== "runner-binding-plan-v1" || typeof value.plan_id !== "string" || !UUID.test(value.plan_id) || typeof value.operator_id !== "string" || typeof value.candidate_record_id !== "string" || !UUID.test(value.candidate_record_id) || !instant(value.recorded_at) || !instant(value.valid_until) || value.record_state !== "recorded" || value.lifecycle !== "active" || value.eligibility !== "binding_planned" || !fixedBlockers(value.blockers) || !isRunnerBindingPlanLinkage(value.linkage) || !reference(value.runner_reference) || !isRunnerBindingLimits(value.limits) || !fp(value.idempotency_key_fingerprint) || !fp(value.request_fingerprint) || !fp(value.plan_fingerprint) || value.evidence_only !== true || !falseFields(value, NO_AUTHORITY.filter((key) => key !== "evidence_only"))) return false;
    const recorded = Date.parse(String(value.recorded_at)); const expiry = Date.parse(String(value.valid_until));
    return expiry > recorded && expiry - recorded <= 30_000;
}

function status(value: unknown) { return obj(value) && exact(value, STATUS) && value.schema === "runner-binding-plan-status-v1" && typeof value.plan_id === "string" && UUID.test(value.plan_id) && instant(value.observed_at) && ["active", "expired"].includes(String(value.lifecycle)) && value.eligibility === "binding_planned" && fixedBlockers(value.blockers) && fp(value.status_fingerprint) && value.evidence_only === true && falseFields(value, ["runner_bound", "execution_authorized", "replay_allowed"]); }
function audit(value: unknown) { return obj(value) && exact(value, AUDIT) && value.schema === "runner-binding-plan-audit-evidence-v1" && ["runner_binding_plan_recorded", "runner_binding_plan_read"].includes(String(value.event)) && ["recorded", "exact_duplicate", "read", "blocked"].includes(String(value.outcome)) && fp(value.operator_fingerprint) && fp(value.candidate_record_fingerprint) && (value.plan_fingerprint === null || fp(value.plan_fingerprint)) && fp(value.correlation_fingerprint) && instant(value.occurred_at) && fp(value.audit_fingerprint) && value.evidence_only === true && falseFields(value, AUDIT_FALSE); }
function redactedError(value: unknown) { return obj(value) && exact(value, ERROR) && value.schema === "runner-binding-plan-redacted-error-v1" && ["malformed", "unauthenticated", "unauthorized", "not_found", "not_eligible", "expired", "conflict", "quota_exceeded", "unavailable"].includes(String(value.error_code)) && value.message === "runner binding plan request could not be completed" && fp(value.correlation_fingerprint) && value.retryable === false && value.redacted === true && value.evidence_only === true && falseFields(value, ["runner_binding_allowed", "execution_authorized", "mutation_allowed", "replay_allowed"]); }

export function parseRunnerBindingPlanResult(value: unknown): RunnerBindingPlanResultV1 {
    if (!obj(value) || !exact(value, RESULT) || value.schema !== "runner-binding-plan-result-v1" || value.evidence_only !== true || !falseFields(value, RESULT_FALSE)) throw new Error("Invalid runner binding plan response.");
    const success = ["recorded", "exact_duplicate", "read"].includes(String(value.disposition));
    if (success ? !plan(value.plan) || !status(value.status) || !audit(value.audit_evidence) || value.error !== null : value.disposition !== "blocked" || value.plan !== null || value.status !== null || value.audit_evidence !== null || !redactedError(value.error)) throw new Error("Invalid runner binding plan response.");
    if (success) {
        const p = value.plan as Record<string, unknown>; const s = value.status as Record<string, unknown>; const a = value.audit_evidence as Record<string, unknown>;
        if (s.plan_id !== p.plan_id || (a.plan_fingerprint as FingerprintV1).value !== (p.plan_fingerprint as FingerprintV1).value || a.outcome !== value.disposition) throw new Error("Invalid runner binding plan response.");
    }
    if (new TextEncoder().encode(JSON.stringify(value)).length > 128 * 1024) throw new Error("Invalid runner binding plan response.");
    return value as unknown as RunnerBindingPlanResultV1;
}

export function parseRunnerBindingPlanCollection(value: unknown): RunnerBindingPlanCollectionV1 {
    if (!obj(value) || !exact(value, COLLECTION) || value.schema !== "runner-binding-plan-collection-v1" || !Array.isArray(value.plans) || value.evidence_only !== true || value.execution_authorized !== false || value.mutation_allowed !== false) throw new Error("Invalid runner binding plan collection.");
    return { ...value, plans: value.plans.map(parseRunnerBindingPlanResult) } as RunnerBindingPlanCollectionV1;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/runner-binding-plans`;
export async function listRunnerBindingPlans(candidateId: string) { const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true }); return parseRunnerBindingPlanCollection(response.data); }
export async function getRunnerBindingPlan(candidateId: string, planId: string) { const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(planId)}`, { withCredentials: true }); return parseRunnerBindingPlanResult(response.data); }
export async function createRunnerBindingPlan(candidateId: string, body: RunnerBindingPlanCreateV1, csrf: string, key: string) { const response = await atlas.post<unknown>(path(candidateId), body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrf, "Idempotency-Key": key } }); return parseRunnerBindingPlanResult(response.data); }
export function runnerBindingPlanIdempotencyKey() { return `mission-control-runner-binding-plan-evidence-${crypto.randomUUID()}`; }
