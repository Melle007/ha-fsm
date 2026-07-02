from __future__ import annotations

from typing import Any, TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from .models import TransitionConfig

if TYPE_CHECKING:
    from .runtime import FSMRuntime

MAX_VARIABLE_RESOLUTION_ITERATIONS = 10
_TEMPLATE_MARKERS = ("{{", "{%", "{#")


def is_template_string(value: str) -> bool:
    return any(marker in value for marker in _TEMPLATE_MARKERS)


def compile_template_value(hass: HomeAssistant, value: Any) -> Any:
    if isinstance(value, str):
        if not is_template_string(value):
            return value

        try:
            return Template(value, hass)
        except Exception as err:
            raise ValueError(f"Invalid FSM template '{value}': {err}") from err

    if isinstance(value, dict):
        return {
            key: compile_template_value(hass, sub_value)
            for key, sub_value in value.items()
        }

    if isinstance(value, list):
        return [compile_template_value(hass, item) for item in value]

    return value


def render_template_value(
    hass: HomeAssistant,
    value: Any,
    variables: dict[str, Any],
    *,
    safe: bool = False,
) -> Any:
    if isinstance(value, Template):
        try:
            return value.async_render(variables, parse_result=True)
        except Exception:
            if safe:
                return value
            raise

    if isinstance(value, str):
        if not is_template_string(value):
            return value

        tpl = Template(value, hass)
        try:
            return tpl.async_render(variables, parse_result=True)
        except Exception:
            if safe:
                return value
            raise

    if isinstance(value, dict):
        return {
            key: render_template_value(hass, sub_value, variables, safe=safe)
            for key, sub_value in value.items()
        }

    if isinstance(value, list):
        return [
            render_template_value(hass, item, variables, safe=safe)
            for item in value
        ]

    return value


def render_fsm_variables(
    hass: HomeAssistant,
    config_variables: dict[str, Any],
    raw_variables: dict[str, Any],
    *,
    iterative: bool = False,
) -> dict[str, Any]:
    if not iterative:
        rendered_variables: dict[str, Any] = {}
        for key, value in (config_variables or {}).items():
            context = {
                **raw_variables,
                **rendered_variables,
                "variables": rendered_variables,
            }
            rendered_variables[key] = render_template_value(
                hass,
                value,
                context,
                safe=False,
            )
        return rendered_variables

    rendered_variables = config_variables or {}

    for _ in range(MAX_VARIABLE_RESOLUTION_ITERATIONS):
        context = {
            **raw_variables,
            **rendered_variables,
            "variables": rendered_variables,
        }
        next_variables = render_template_value(
            hass,
            config_variables,
            context,
            safe=True,
        )
        if next_variables == rendered_variables:
            return next_variables
        rendered_variables = next_variables

    return rendered_variables


def build_fsm_context(
    hass: HomeAssistant,
    fsm_runtime: FSMRuntime,
    trigger_payload: dict[str, Any] | None,
    transition: TransitionConfig | None = None,
    *,
    trigger_id: str | None = None,
    state: str | None = None,
    previous_state: str | None = None,
) -> dict[str, Any]:
    current_state = state if state is not None else fsm_runtime.state
    raw_variables = {
        "fsm": {
            "id": fsm_runtime.config.id,
            "name": fsm_runtime.config.name,
            "state": current_state,
            "previous_state": previous_state
            if previous_state is not None
            else fsm_runtime.previous_state,
        },
        "variables": fsm_runtime.config.variables,
        "trigger": (trigger_payload or {}).get("trigger", trigger_payload or {}),
        "trigger_id": trigger_id or fsm_runtime.last_trigger_id,
    }

    if transition is not None:
        raw_variables.update(
            {
                "transition": {
                    "from": transition.from_state,
                    "to": transition.to_state,
                    "trigger_id": transition.trigger_id,
                },
                "from_state": transition.from_state,
                "to_state": transition.to_state,
            }
        )

    rendered_variables = render_fsm_variables(
        hass,
        fsm_runtime.config.variables,
        raw_variables,
    )

    return {
        **raw_variables,
        **rendered_variables,
        "variables": rendered_variables,
    }
