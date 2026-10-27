import type {
    ManagedProviderResourceV2,
    ManagedProviderResourceV3,
    ProviderManagementV2,
    ProviderManagementV3,
} from "../types/providerManagement";
import type {
    ProviderResource,
    ProviderResourceCollection,
} from "../types/resources";

export type Coordinate = `${string}\u0000${string}\u0000${string}`;
export type ComposedResource = {
    coordinate: Coordinate;
    inventory: ProviderResource | null;
    management: ManagedProviderResourceV2 | null;
    operator: ManagedProviderResourceV3 | null;
    inconsistent: boolean;
};

export function coordinate(
    providerId: string,
    resourceType: string,
    resourceId: string,
): Coordinate {
    return `${providerId}\u0000${resourceType}\u0000${resourceId}`;
}

function resourceCoordinate(resource: {
    provider_id: string;
    resource_type: string;
    resource_id: string;
}): Coordinate {
    return coordinate(
        resource.provider_id,
        resource.resource_type,
        resource.resource_id,
    );
}

export function composeProviderResources(
    inventory: ProviderResourceCollection | null,
    management: ProviderManagementV2 | null,
    operator: ProviderManagementV3 | null,
): ComposedResource[] {
    const inventoryByCoordinate = new Map<Coordinate, ProviderResource>();
    const managementByCoordinate = new Map<Coordinate, ManagedProviderResourceV2>();
    const operatorByCoordinate = new Map<Coordinate, ManagedProviderResourceV3>();
    const managementTypesById = new Map<string, Set<string>>();

    for (const resource of inventory?.resources ?? []) {
        const key = resourceCoordinate(resource);
        if (inventoryByCoordinate.has(key)) {
            throw new Error("Observed resource coordinates are duplicated.");
        }
        inventoryByCoordinate.set(key, resource);
    }
    for (const resource of management?.resources ?? []) {
        const key = resourceCoordinate(resource);
        if (managementByCoordinate.has(key)) {
            throw new Error("Public management coordinates are duplicated.");
        }
        managementByCoordinate.set(key, resource);
        const idKey = `${resource.provider_id}\u0000${resource.resource_id}`;
        const types = managementTypesById.get(idKey) ?? new Set<string>();
        types.add(resource.resource_type);
        managementTypesById.set(idKey, types);
    }
    for (const resource of operator?.resources ?? []) {
        const key = resourceCoordinate(resource);
        if (operatorByCoordinate.has(key)) {
            throw new Error("Operator management coordinates are duplicated.");
        }
        operatorByCoordinate.set(key, resource);
    }

    const keys = new Set([
        ...inventoryByCoordinate.keys(),
        ...managementByCoordinate.keys(),
    ]);
    return [...keys].sort().map((key) => {
        const observed = inventoryByCoordinate.get(key) ?? null;
        const authoritative = managementByCoordinate.get(key) ?? null;
        const overlay = operatorByCoordinate.get(key) ?? null;
        const conflictingTypes = observed
            ? managementTypesById.get(
                `${observed.provider_id}\u0000${observed.resource_id}`,
            )
            : undefined;
        return {
            coordinate: key,
            inventory: observed,
            management: authoritative,
            operator: authoritative && overlay ? overlay : null,
            inconsistent: Boolean(
                observed && !authoritative && conflictingTypes?.size,
            ),
        };
    });
}

export function monitoringPresentation(
    managed: ManagedProviderResourceV2 | null,
    observedState: string | null,
    unavailable: boolean,
) {
    if (unavailable || !managed) {
        return {
            identity: "Unavailable",
            expectation: "Monitoring unavailable",
            status: "Monitoring unavailable — monitoring settings could not be loaded",
        };
    }
    const identity = managed.identity_assurance === "authoritative" ? "Verified" : formatLabel(managed.identity_assurance);
    const expectation = managed.expectation === "ignored"
        ? "Ignored"
        : managed.expectation
          ? `Expected ${managed.expectation}`
          : managed.intent_status === "unsupported"
            ? "Unsupported"
            : managed.intent_status === "unavailable"
              ? "Unavailable"
              : "Not configured";
    if (managed.intent_status === "configured" && managed.expectation) {
        if (managed.expectation === "ignored") {
            return { identity, expectation, status: "Configured — monitoring ignored" };
        }
        return {
            identity,
            expectation,
            status: observedState === null || observedState === "unknown"
                ? "Configured — observed state unavailable"
                : managed.expectation === observedState
                    ? "Configured — matches observed state"
                    : "Configured — does not match observed state",
        };
    }
    const statuses: Record<string, string> = {
        no_active_intent: "No monitoring setting has been chosen.",
        legacy_unbound_evidence: "A previous monitoring setting is available to review.",
        incarnation_mismatch: "The resource identity changed. Review the monitoring setting.",
        identity_unavailable: "Atlas could not verify this resource’s identity.",
        authority_store_unavailable: "Monitoring unavailable — monitoring settings could not be loaded",
        resource_missing: "Resource missing — the saved setting is kept for reference",
        resource_type_unsupported: "Monitoring settings are not supported for this resource type",
    };
    return {
        identity,
        expectation,
        status: statuses[managed.intent_reason] ?? formatLabel(managed.intent_status),
    };
}

export function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
