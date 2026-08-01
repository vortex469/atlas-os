from collections import Counter, defaultdict

from app.clients.homeassistant_client import (
    get_api_status,
    get_states,
)
from app.context import AtlasContext


def get_homeassistant_status(
    atlas_context: AtlasContext | None = None,
) -> dict:
    api = get_api_status(atlas_context)
    states = get_states(atlas_context)

    domains = Counter(
        state["entity_id"].split(".", 1)[0]
        for state in states
    )

    unavailable = [
        {
            "entity_id": state["entity_id"],
            "name": state.get("attributes", {}).get(
                "friendly_name",
                state["entity_id"],
            ),
            "state": state.get("state"),
        }
        for state in states
        if state.get("state") in {"unavailable", "unknown"}
    ]

    updates = [
        {
            "entity_id": state["entity_id"],
            "name": state.get("attributes", {}).get(
                "friendly_name",
                state["entity_id"],
            ),
            "installed_version": state.get("attributes", {}).get(
                "installed_version"
            ),
            "latest_version": state.get("attributes", {}).get(
                "latest_version"
            ),
        }
        for state in states
        if state["entity_id"].startswith("update.")
        and state.get("state") == "on"
    ]

    zwave_entities = [
        {
            "entity_id": state["entity_id"],
            "name": state.get("attributes", {}).get(
                "friendly_name",
                state["entity_id"],
            ),
            "state": state.get("state"),
        }
        for state in states
        if "zwave" in state["entity_id"].lower()
        or "zwave" in str(state.get("attributes", {})).lower()
    ]

    return {
        "status": "online",
        "api_message": api.get("message"),
        "entities": {
            "total": len(states),
            "domains": dict(sorted(domains.items())),
            "unavailable_count": len(unavailable),
        },
        "updates": {
            "pending_count": len(updates),
            "items": updates,
        },
        "zwave": {
            "entity_count": len(zwave_entities),
            "entities": zwave_entities,
        },
        "unavailable_entities": unavailable,
    }

def get_unavailable_entities(
    atlas_context: AtlasContext | None = None,
) -> dict:
    states = get_states(atlas_context)

    grouped: dict[str, list[dict]] = defaultdict(list)

    for state in states:
        entity_state = state.get("state")

        if entity_state not in {"unavailable", "unknown"}:
            continue

        entity_id = state["entity_id"]
        domain = entity_id.split(".", 1)[0]
        attributes = state.get("attributes", {})

        grouped[domain].append(
            {
                "entity_id": entity_id,
                "name": attributes.get(
                    "friendly_name",
                    entity_id,
                ),
                "state": entity_state,
                "device_class": attributes.get("device_class"),
                "integration": attributes.get("integration"),
            }
        )

    sorted_groups = {
        domain: sorted(
            entities,
            key=lambda item: item["name"].lower(),
        )
        for domain, entities in sorted(grouped.items())
    }

    return {
        "total": sum(
            len(entities)
            for entities in sorted_groups.values()
        ),
        "domain_count": len(sorted_groups),
        "domains": {
            domain: {
                "count": len(entities),
                "entities": entities,
            }
            for domain, entities in sorted_groups.items()
        },
    }
