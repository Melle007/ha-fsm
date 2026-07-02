from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_RUNTIMES,
    DOMAIN,
    SERVICE_FIELD_ENTITY_ID,
    SERVICE_FIELD_FSM_ID,
    SERVICE_FIELD_STATE,
    SERVICE_FIELD_TRIGGER_ID,
    SERVICE_SET_STATE,
    SERVICE_TRIGGER,
)
from .exceptions import FSMRuntimeError

if TYPE_CHECKING:
    from .runtime import FSMRuntime

_LOGGER = logging.getLogger(__name__)


async def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_TRIGGER):
        return

    def _resolve_runtime(call: ServiceCall) -> FSMRuntime:
        runtimes = hass.data[DOMAIN][DATA_RUNTIMES]
        fsm_id = call.data.get(SERVICE_FIELD_FSM_ID)
        entity_id = call.data.get(SERVICE_FIELD_ENTITY_ID)

        if fsm_id is not None and entity_id is not None:
            runtime = runtimes.get(fsm_id)
            if runtime is None:
                raise ServiceValidationError(f"Unknown FSM id: {fsm_id}")
            if runtime.entity is None or runtime.entity.entity_id != entity_id:
                raise ServiceValidationError(
                    f"Conflicting FSM target: fsm_id '{fsm_id}' does not match entity_id '{entity_id}'"
                )
            return runtime

        if fsm_id is not None:
            runtime = runtimes.get(fsm_id)
            if runtime is None:
                raise ServiceValidationError(f"Unknown FSM id: {fsm_id}")
            return runtime

        if entity_id is not None:
            runtime = next(
                (
                    rt
                    for rt in runtimes.values()
                    if rt.entity and rt.entity.entity_id == entity_id
                ),
                None,
            )
            if runtime is None:
                raise ServiceValidationError(f"Unknown FSM entity_id: {entity_id}")
            return runtime

        raise ServiceValidationError("Either fsm_id or entity_id must be provided")

    async def handle_trigger(call: ServiceCall) -> None:
        runtime = _resolve_runtime(call)
        trigger_id = call.data[SERVICE_FIELD_TRIGGER_ID]
        await runtime.async_handle_trigger(trigger_id, {"service": True}, call.context)

    async def handle_set_state(call: ServiceCall) -> None:
        runtime = _resolve_runtime(call)
        state = call.data[SERVICE_FIELD_STATE]

        try:
            await runtime.async_force_state(state)
        except FSMRuntimeError as err:
            raise ServiceValidationError(str(err)) from err

    trigger_schema = vol.Schema(
        vol.Any(
            {
                vol.Required(SERVICE_FIELD_FSM_ID): cv.string,
                vol.Required(SERVICE_FIELD_TRIGGER_ID): cv.string,
                vol.Optional(SERVICE_FIELD_ENTITY_ID): cv.entity_id,
            },
            {
                vol.Required(SERVICE_FIELD_ENTITY_ID): cv.entity_id,
                vol.Required(SERVICE_FIELD_TRIGGER_ID): cv.string,
                vol.Optional(SERVICE_FIELD_FSM_ID): cv.string,
            },
        )
    )

    set_state_schema = vol.Schema(
        vol.Any(
            {
                vol.Required(SERVICE_FIELD_FSM_ID): cv.string,
                vol.Required(SERVICE_FIELD_STATE): cv.string,
                vol.Optional(SERVICE_FIELD_ENTITY_ID): cv.entity_id,
            },
            {
                vol.Required(SERVICE_FIELD_ENTITY_ID): cv.entity_id,
                vol.Required(SERVICE_FIELD_STATE): cv.string,
                vol.Optional(SERVICE_FIELD_FSM_ID): cv.string,
            },
        )
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIGGER,
        handle_trigger,
        schema=trigger_schema,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_STATE,
        handle_set_state,
        schema=set_state_schema,
    )
