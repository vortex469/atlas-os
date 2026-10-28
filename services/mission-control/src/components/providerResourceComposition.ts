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
            identity: "Unable to verify",
            expectation: "Monitoring unavailable",
            status: "Monitoring unavailable — Atlas could not load monitoring settings",
        };
    }
    const identity = identityLabel(managed.identity_assurance);
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
            status: observedState !== null && managed.expectation === observedState
                ? "Configured — matches observed state"
                : "Configured — does not match observed state",
        };
    }
    const statuses: Record<string, string> = {
        no_active_intent: "Needs review — no monitoring expectation is set",
        legacy_unbound_evidence: "Needs review — an older monitoring setting is available for reference",
        incarnation_mismatch: "Needs review — this VM was replaced",
        identity_unavailable: "Needs review — Atlas cannot verify this VM's identity",
        authority_store_unavailable: "Monitoring unavailable — Atlas could not load monitoring settings",
        resource_missing: "Resource missing — its saved monitoring setting does not apply to a current instance",
        resource_type_unsupported: "Monitoring is not supported for this resource type",
    };
    return {
        identity,
        expectation,
        status: statuses[managed.intent_reason] ?? formatLabel(managed.intent_status),
    };
}

function identityLabel(
    assurance: "authoritative" | "unavailable" | "unsupported",
): string {
    switch (assurance) {
        case "authoritative":
            return "Provider verified";
        case "unsupported":
            return "Not supported";
        case "unavailable":
            return "Unable to verify";
    }
}

export function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
