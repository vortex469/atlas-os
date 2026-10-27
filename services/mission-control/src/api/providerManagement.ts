import { atlas } from "./atlas";
import { parseMonitoringReceipt } from "./monitoringReceipt";
import type {
    ProviderIntentMutationRequest,
    ProviderIntentMutationResult,
    ManagedProviderResourceV2,
    ProviderManagementV2,
    ProviderManagementV3,
    ProviderManagementSectionDescriptor,
    ProviderResourceManagementSupportV2,
} from "../types/providerManagement";

const sections = new Set(["connection", "discovery", "resources", "monitoring", "diagnostics", "actions"]);
const identityAssurances = new Set(["authoritative", "unavailable", "unsupported"]);
const intentStatuses = new Set(["configured", "needs_review", "missing", "unsupported", "unavailable"]);
const intentReasons = new Set([
    "legacy_policy_match", "no_legacy_policy", "matching_active_intent", "no_active_intent",
    "legacy_unbound_evidence", "incarnation_mismatch", "identity_unavailable", "resource_missing",
    "resource_type_unsupported", "authority_store_unavailable",
]);
const expectations = new Set(["running", "stopped", "ignored"]);
const canonicalExpectations = ["running", "stopped", "ignored"];
const fingerprintPattern = /^provider-management-fingerprint-v1:[a-f0-9]{64}$/;
const providerKeyPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function object(value: unknown, fields: readonly string[], label: string): Record<string, unknown> {
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`${label} is invalid.`);
    const result = value as Record<string, unknown>;
    if (Object.keys(result).sort().join("|") !== [...fields].sort().join("|")) throw new Error(`${label} fields are invalid.`);
    return result;
}

function string(value: unknown, label: string): string {
    if (typeof value !== "string" || value.length === 0) throw new Error(`${label} is invalid.`);
    return value;
}

function boolean(value: unknown, label: string): boolean {
    if (typeof value !== "boolean") throw new Error(`${label} is invalid.`);
    return value;
}

function falseValue(value: unknown, label: string): false {
    if (value !== false) throw new Error(`${label} must be false.`);
    return false;
}

function enumValue<T extends string>(value: unknown, allowed: Set<string>, label: string): T {
    if (typeof value !== "string" || !allowed.has(value)) throw new Error(`${label} is invalid.`);
    return value as T;
}

function expectation(value: unknown, label: string) {
    return value === null ? null : enumValue<"running" | "stopped" | "ignored">(value, expectations, label);
}

export function parseProviderManagementV2(value: unknown): ProviderManagementV2 {
    const root = object(value, [
        "schema_version", "provider_id", "provider_name", "sections", "resource_types", "resources",
        "provider_intent_activation", "provider_intent_authority_status", "grants_permission", "grants_execution",
    ], "provider management v2");
    if (root.schema_version !== "provider-management-v2") throw new Error("Provider management schema is invalid.");
    if (!Array.isArray(root.sections) || !Array.isArray(root.resource_types) || !Array.isArray(root.resources)) {
        throw new Error("Provider management collections are invalid.");
    }
    const providerId = string(root.provider_id, "provider id");
    if (!providerKeyPattern.test(providerId)) throw new Error("Provider id is invalid.");
    const parsedSections: ProviderManagementSectionDescriptor[] = root.sections.map((entry) => {
        const item = object(entry, ["section", "availability", "read_only_descriptor", "grants_permission", "grants_execution"], "management section");
        if (item.read_only_descriptor !== true) throw new Error("Management section must be read-only.");
        return {
            section: enumValue<ProviderManagementSectionDescriptor["section"]>(item.section, sections, "management section"),
            availability: enumValue<ProviderManagementSectionDescriptor["availability"]>(item.availability, new Set(["available", "unavailable"]), "section availability"),
            read_only_descriptor: true as const,
            grants_permission: falseValue(item.grants_permission, "section permission"),
            grants_execution: falseValue(item.grants_execution, "section execution"),
        };
    });
    if (parsedSections.length !== sections.size || new Set(parsedSections.map((item) => item.section)).size !== sections.size) {
        throw new Error("Provider management sections must be complete and unique.");
    }
    const supportCoordinates = new Set<string>();
    const parsedTypes: ProviderResourceManagementSupportV2[] = root.resource_types.map((entry) => {
        const item = object(entry, ["provider_id", "resource_type", "resource_readable", "authoritative_identity_supported", "provider_intent_capability_supported", "provider_intent_mutation_available", "supported_expectations", "operationally_requestable", "grants_permission", "grants_execution"], "resource support");
        if (!Array.isArray(item.supported_expectations)) throw new Error("Supported expectations are invalid.");
        const itemProvider = string(item.provider_id, "support provider id");
        if (itemProvider !== providerId) throw new Error("Resource support provider disagrees.");
        const resourceType = string(item.resource_type, "resource type");
        if (!providerKeyPattern.test(resourceType)) throw new Error("Resource type is invalid.");
        const supportCoordinate = `${itemProvider}\u0000${resourceType}`;
        if (supportCoordinates.has(supportCoordinate)) throw new Error("Resource support coordinates are duplicated.");
        supportCoordinates.add(supportCoordinate);
        const supportedExpectations = item.supported_expectations.map((entry) => enumValue<ProviderResourceManagementSupportV2["supported_expectations"][number]>(entry, expectations, "supported expectation"));
        if (supportedExpectations.join("|") !== canonicalExpectations.filter((entry) => supportedExpectations.includes(entry as ProviderResourceManagementSupportV2["supported_expectations"][number])).join("|")) throw new Error("Supported expectations are not canonical.");
        const resourceReadable = boolean(item.resource_readable, "resource readability");
        const identitySupported = boolean(item.authoritative_identity_supported, "identity support");
        const intentSupported = boolean(item.provider_intent_capability_supported, "intent support");
        if ((!resourceReadable && (identitySupported || intentSupported || supportedExpectations.length > 0)) || (intentSupported && !identitySupported) || Boolean(supportedExpectations.length) !== intentSupported) throw new Error("Resource support combination is invalid.");
        return {
            provider_id: itemProvider,
            resource_type: resourceType,
            resource_readable: resourceReadable,
            authoritative_identity_supported: identitySupported,
            provider_intent_capability_supported: intentSupported,
            provider_intent_mutation_available: falseValue(item.provider_intent_mutation_available, "public mutation"),
            supported_expectations: supportedExpectations,
            operationally_requestable: falseValue(item.operationally_requestable, "operational requestability"),
            grants_permission: falseValue(item.grants_permission, "support permission"),
            grants_execution: falseValue(item.grants_execution, "support execution"),
        };
    });
    const sortedSupportCoordinates = [...supportCoordinates].sort();
    if ([...supportCoordinates].join("|") !== sortedSupportCoordinates.join("|")) throw new Error("Resource support is not deterministically ordered.");
    const coordinates = new Set<string>();
    const parsedResources: ManagedProviderResourceV2[] = root.resources.map((entry) => {
        const item = object(entry, ["provider_id", "resource_id", "resource_type", "display_name", "current_state", "missing", "identity_assurance", "management_fingerprint", "intent_authority", "intent_status", "intent_reason", "expectation", "record_version", "legacy_review_available", "legacy_expectation", "replacement_detected", "mutation_available", "operationally_requestable", "grants_execution"], "managed resource");
        const itemProvider = string(item.provider_id, "resource provider id");
        const resourceType = string(item.resource_type, "resource type");
        const resourceId = string(item.resource_id, "resource id");
        const coordinate = `${itemProvider}\u0000${resourceType}\u0000${resourceId}`;
        if (itemProvider !== providerId || coordinates.has(coordinate)) throw new Error("Managed resource coordinates are invalid or duplicated.");
        coordinates.add(coordinate);
        const fingerprint = item.management_fingerprint;
        if (fingerprint !== null && (typeof fingerprint !== "string" || !fingerprintPattern.test(fingerprint))) throw new Error("Management fingerprint is invalid.");
        const recordVersion = item.record_version;
        if (recordVersion !== null && (!Number.isInteger(recordVersion) || Number(recordVersion) < 1)) throw new Error("Record version is invalid.");
        const identityAssurance = enumValue<ManagedProviderResourceV2["identity_assurance"]>(item.identity_assurance, identityAssurances, "identity assurance");
        const intentAuthority = enumValue<ManagedProviderResourceV2["intent_authority"]>(item.intent_authority, new Set(["legacy_policy", "provider_intent"]), "intent authority");
        const intentStatus = enumValue<ManagedProviderResourceV2["intent_status"]>(item.intent_status, intentStatuses, "intent status");
        const intentReason = enumValue<ManagedProviderResourceV2["intent_reason"]>(item.intent_reason, intentReasons, "intent reason");
        const parsedExpectation = expectation(item.expectation, "expectation");
        const legacyExpectation = expectation(item.legacy_expectation, "legacy expectation");
        const legacyReviewAvailable = boolean(item.legacy_review_available, "legacy review availability");
        const replacementDetected = boolean(item.replacement_detected, "replacement state");
        if ((identityAssurance === "authoritative") !== (fingerprint !== null)) throw new Error("Identity assurance and fingerprint disagree.");
        const configuredProviderIntent = intentAuthority === "provider_intent" && (intentStatus === "configured" || intentStatus === "missing");
        if (configuredProviderIntent !== (recordVersion !== null) || (configuredProviderIntent && parsedExpectation === null)) throw new Error("Provider Intent configuration is incomplete.");
        if (legacyReviewAvailable !== (legacyExpectation !== null) || replacementDetected !== (intentReason === "incarnation_mismatch")) throw new Error("Historical Provider Intent context is inconsistent.");
        const validReasons: Record<ManagedProviderResourceV2["intent_authority"], Partial<Record<ManagedProviderResourceV2["intent_status"], Set<ManagedProviderResourceV2["intent_reason"]>>>> = {
            legacy_policy: {
                configured: new Set(["legacy_policy_match"]),
                missing: new Set(["legacy_policy_match"]),
                needs_review: new Set(["no_legacy_policy"]),
            },
            provider_intent: {
                configured: new Set(["matching_active_intent"]),
                missing: new Set(["resource_missing"]),
                needs_review: new Set(["no_active_intent", "legacy_unbound_evidence", "incarnation_mismatch", "identity_unavailable"]),
                unsupported: new Set(["resource_type_unsupported"]),
                unavailable: new Set(["authority_store_unavailable"]),
            },
        };
        if (!validReasons[intentAuthority][intentStatus]?.has(intentReason)) throw new Error("Provider Intent authority, status, and reason contradict.");
        if (intentAuthority === "provider_intent" && intentStatus === "configured" && identityAssurance !== "authoritative") throw new Error("Configured Provider Intent requires authoritative identity.");
        if (intentStatus === "missing" && identityAssurance === "authoritative") throw new Error("Missing resources cannot claim authoritative identity.");
        return {
            provider_id: itemProvider,
            resource_id: resourceId,
            resource_type: resourceType,
            display_name: string(item.display_name, "display name"),
            current_state: string(item.current_state, "current state"),
            missing: boolean(item.missing, "missing state"),
            identity_assurance: identityAssurance,
            management_fingerprint: fingerprint,
            intent_authority: intentAuthority,
            intent_status: intentStatus,
            intent_reason: intentReason,
            expectation: parsedExpectation,
            record_version: recordVersion as number | null,
            legacy_review_available: legacyReviewAvailable,
            legacy_expectation: legacyExpectation,
            replacement_detected: replacementDetected,
            mutation_available: falseValue(item.mutation_available, "public mutation"),
            operationally_requestable: falseValue(item.operationally_requestable, "operational requestability"),
            grants_execution: falseValue(item.grants_execution, "resource execution"),
        };
    });
    return {
        schema_version: "provider-management-v2",
        provider_id: providerId,
        provider_name: string(root.provider_name, "provider name"),
        sections: parsedSections,
        resource_types: parsedTypes,
        resources: parsedResources,
        provider_intent_activation: enumValue(root.provider_intent_activation, new Set(["not_activated", "activated"]), "Provider Intent activation"),
        provider_intent_authority_status: enumValue(root.provider_intent_authority_status, new Set(["available", "unavailable"]), "Provider Intent authority"),
        grants_permission: falseValue(root.grants_permission, "descriptor permission"),
        grants_execution: falseValue(root.grants_execution, "descriptor execution"),
    };
}

export async function getProviderManagement(providerId: string): Promise<ProviderManagementV2> {
    const response = await atlas.get<unknown>(
        `/providers/${encodeURIComponent(providerId)}/management`,
    );
    return parseProviderManagementV2(response.data);
}

export function parseProviderManagementV3(value: unknown, requestedProviderId: string): ProviderManagementV3 {
    const root = object(value, ["schema_version", "provider_id", "provider_name", "sections", "resource_types", "resources",
        "provider_intent_activation", "provider_intent_authority_status", "caller_has_provider_intent_update", "grants_permission", "grants_execution"], "operator management");
    if (root.schema_version !== "provider-management-v3" || root.provider_id !== requestedProviderId) throw new Error("Operator management provider or schema is invalid.");
    if (!Array.isArray(root.resources) || !Array.isArray(root.resource_types)) throw new Error("Operator management collections are invalid.");
    const callerHasPermission = boolean(root.caller_has_provider_intent_update, "operator capability");
    const privateRows = root.resources.map(entry => {
        const row = object(entry, ["provider_id", "resource_id", "resource_type", "display_name", "current_state", "missing", "resource_live", "identity_assurance", "management_fingerprint", "intent_authority", "intent_status", "intent_reason", "expectation", "record_version", "legacy_review_available", "legacy_expectation", "replacement_detected", "provider_intent_mutation_supported", "mutation_readiness", "editable_in_principle", "caller_can_mutate", "operationally_requestable", "grants_permission", "grants_execution"], "operator resource");
        const { resource_live, provider_intent_mutation_supported, mutation_readiness, editable_in_principle, caller_can_mutate, grants_permission, ...publicFields } = row;
        return {
            publicFields: { ...publicFields, mutation_available: false },
            resource_live: boolean(resource_live, "live resource"),
            provider_intent_mutation_supported: boolean(provider_intent_mutation_supported, "mutation support"),
            mutation_readiness: enumValue<ProviderManagementV3["resources"][number]["mutation_readiness"]>(mutation_readiness,
                new Set(["ready", "not_activated", "authority_unavailable", "store_migration_required", "store_unavailable", "resource_missing", "identity_unavailable", "resource_type_unsupported"]), "mutation readiness"),
            editable_in_principle: boolean(editable_in_principle, "editability"),
            caller_can_mutate: boolean(caller_can_mutate, "caller mutation"),
            grants_permission: falseValue(grants_permission, "resource permission"),
        };
    });
    const privateTypes = root.resource_types.map(entry => {
        const item = object(entry, ["provider_id", "resource_type", "resource_readable", "authoritative_identity_supported", "provider_intent_capability_supported", "provider_intent_mutation_supported", "supported_expectations", "operationally_requestable", "grants_permission", "grants_execution"], "operator resource support");
        const { provider_intent_mutation_supported, ...publicFields } = item;
        return { publicFields: { ...publicFields, provider_intent_mutation_available: false },
            supported: boolean(provider_intent_mutation_supported, "type mutation support") };
    });
    const { caller_has_provider_intent_update, ...publicRoot } = root;
    void caller_has_provider_intent_update;
    const parsed = parseProviderManagementV2({ ...publicRoot, schema_version: "provider-management-v2",
        resources: privateRows.map(row => row.publicFields), resource_types: privateTypes.map(item => item.publicFields) });
    const resources: ProviderManagementV3["resources"] = parsed.resources.map((row, index) => {
        const { mutation_available, ...facts } = row;
        void mutation_available;
        const { publicFields, ...privateFields } = privateRows[index];
        void publicFields;
        const result = { ...facts, ...privateFields };
        const ready = result.mutation_readiness === "ready";
        if (result.resource_id.includes("\u0000") || result.resource_type.includes("\u0000")) throw new Error("Operator resource coordinate is ambiguous.");
        if (result.record_version !== null && !Number.isSafeInteger(result.record_version)) throw new Error("Operator record version is not browser safe.");
        if (result.resource_live === result.missing
            || (!result.provider_intent_mutation_supported && result.mutation_readiness !== "resource_type_unsupported")
            || result.editable_in_principle !== ready
            || (ready && !(result.provider_id === "proxmox" && result.resource_type === "qemu" && result.provider_intent_mutation_supported && result.resource_live && result.identity_assurance === "authoritative"))
            || (result.caller_can_mutate && (!result.editable_in_principle || !callerHasPermission))
            || ((result.intent_status === "configured" || result.intent_status === "missing") !== (result.record_version !== null))
            || (ready && (parsed.provider_intent_activation !== "activated" || parsed.provider_intent_authority_status !== "available"))) throw new Error("Operator resource readiness contradicts its context.");
        return result;
    });
    const keys = resources.map(row => `${row.provider_id}\u0000${row.resource_type}\u0000${row.resource_id}`);
    if (JSON.stringify(keys) !== JSON.stringify([...keys].sort((left, right) => {
        const a = Array.from(left, c => c.codePointAt(0) ?? 0), b = Array.from(right, c => c.codePointAt(0) ?? 0);
        for (let index = 0; index < Math.min(a.length, b.length); index += 1) if (a[index] !== b[index]) return a[index] - b[index];
        return a.length - b.length;
    }))) throw new Error("Operator resources must be ordered.");
    const resourceTypes: ProviderManagementV3["resource_types"] = parsed.resource_types.map((item, index) => {
        const { provider_intent_mutation_available, ...facts } = item;
        void provider_intent_mutation_available;
        const supported = privateTypes[index].supported;
        if (supported && !(item.provider_id === "proxmox" && item.resource_type === "qemu" && item.resource_readable && item.authoritative_identity_supported && item.provider_intent_capability_supported && item.supported_expectations.length > 0)) throw new Error("Operator type mutation support is invalid.");
        return { ...facts, provider_intent_mutation_supported: supported };
    });
    return { ...parsed, schema_version: "provider-management-v3", caller_has_provider_intent_update: callerHasPermission, resources, resource_types: resourceTypes };
}

export async function getAuthenticatedProviderManagement(
    providerId: string,
): Promise<ProviderManagementV3> {
    const response = await atlas.get<unknown>(
        `/providers/${encodeURIComponent(providerId)}/management/operator`,
        { withCredentials: true },
    );
    return parseProviderManagementV3(response.data, providerId);
}

export async function putProviderMonitoringIntent(
    providerId: string,
    resourceType: string,
    resourceId: string,
    request: ProviderIntentMutationRequest,
    csrfToken: string,
): Promise<ProviderIntentMutationResult> {
    const submittedRequest = { ...request };
    const response = await atlas.put<unknown>(
        `/providers/${encodeURIComponent(providerId)}/management/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}/monitoring-intent`,
        submittedRequest,
        {
            withCredentials: true,
            headers: { "X-Atlas-CSRF-Token": csrfToken },
        },
    );
    return parseMonitoringReceipt(response.data, providerId, resourceType, resourceId, submittedRequest);
}
