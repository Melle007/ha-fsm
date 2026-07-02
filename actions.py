from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.script import Script

from .action_validation import normalize_actions
from .exceptions import FSMActionError
from .templating import (
    build_fsm_context,
    compile_template_value,
    render_template_value,
)

if TYPE_CHECKING:
    from .runtime import FSMRuntime

_LOGGER = logging.getLogger(__name__)


def compile_action_item(
    hass: HomeAssistant,
    action: dict[str, object],
) -> dict[str, object]:
    return {
        key: compile_template_value(hass, value)
        for key, value in action.items()
    }


def compile_actions(
    hass: HomeAssistant,
    actions: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [compile_action_item(hass, action) for action in actions]


def render_action_item(
    hass: HomeAssistant,
    action: dict[str, object],
    variables: dict[str, object],
) -> dict[str, object]:
    return {
        key: render_template_value(hass, value, variables)
        for key, value in action.items()
    }


async def run_actions(
    hass: HomeAssistant,
    fsm_runtime: FSMRuntime,
    actions: list[dict[str, Any]],
    trigger_payload: dict[str, object] | None,
    context: Context | None = None,
    already_normalized: bool = False,
    rendered_context: dict[str, object] | None = None,
) -> None:
    if not actions:
        return

    variables = rendered_context or build_fsm_context(
        hass,
        fsm_runtime,
        trigger_payload,
        trigger_id=fsm_runtime.last_trigger_id,
    )

    normalized_actions = actions if already_normalized else normalize_actions(actions)

    try:
        rendered_actions = [
            render_action_item(hass, action, variables)
            for action in normalized_actions
        ]
    except Exception as err:
        _LOGGER.exception(
            "FSM '%s' failed to render transition action templates: %s",
            fsm_runtime.config.id,
            err,
        )
        raise FSMActionError(str(err)) from err

    script = Script(
        hass,
        rendered_actions,
        f"FSM {fsm_runtime.config.id} transition actions",
        domain="fsm",
    )

    try:
        await script.async_run(
            run_variables=variables,
            context=context or Context(),
        )
    except Exception as err:
        _LOGGER.exception(
            "Action execution failed for FSM '%s': %s",
            fsm_runtime.config.id,
            err,
        )
        raise FSMActionError(str(err)) from err
