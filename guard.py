from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from .models import TransitionConfig
from .templating import build_fsm_context

if TYPE_CHECKING:
    from .runtime import FSMRuntime

_LOGGER = logging.getLogger(__name__)


async def evaluate_guard(
    hass: HomeAssistant,
    fsm_runtime: FSMRuntime,
    transition: TransitionConfig,
    trigger_payload: dict[str, Any] | None,
    compiled_template: Template | None = None,
    rendered_context: dict[str, Any] | None = None,
) -> bool:
    if not transition.guard:
        return True

    tpl = compiled_template if compiled_template else Template(transition.guard, hass)
    if rendered_context is None:
        rendered_context = build_fsm_context(
            hass,
            fsm_runtime,
            trigger_payload,
            transition,
            trigger_id=transition.trigger_id,
        )

    try:
        rendered = tpl.async_render(rendered_context, parse_result=True)
        result = bool(rendered)
        if not result:
            _LOGGER.debug(
                "Guard evaluated to false for FSM '%s' transition %s -> %s",
                fsm_runtime.config.id,
                transition.from_state,
                transition.to_state,
            )
        return result
    except Exception as err:
        _LOGGER.exception(
            "Guard evaluation failed for FSM '%s' transition %s -> %s: %s",
            fsm_runtime.config.id,
            transition.from_state,
            transition.to_state,
            err,
        )
        return False
