from collections import Counter

from app.clients.homeassistant_client import (
    get_api_status,
    get_states,
)


def get_homeassistant_status() -> dict:
    api = get_api_status()
    states = get_states()

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
