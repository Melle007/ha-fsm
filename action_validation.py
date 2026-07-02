from __future__ import annotations

from typing import Any


def normalize_action_item(action: Any) -> dict[str, Any]:
    """Validate and normalize a single action mapping."""
    if not isinstance(action, dict):
        raise ValueError("FSM actions must be mappings using 'action:'")

    if "service" in action:
        raise ValueError("FSM actions must use 'action:' instead of 'service:'")

    if "service_template" in action:
        raise ValueError(
            "FSM actions must use 'action:' instead of 'service_template:'"
        )

    if "action" not in action:
        raise ValueError("FSM action mapping requires 'action:'")

    if not isinstance(action["action"], str):
        raise ValueError("'action' must be a string")

    return action


def normalize_actions(actions: list[Any]) -> list[dict[str, Any]]:
    """Validate and normalize a list of action mappings."""
    return [normalize_action_item(action) for action in actions]
