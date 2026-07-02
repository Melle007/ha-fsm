from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import (
    DATA_CONFIGS,
    DATA_ENTITIES,
    DATA_PENDING_ENTITIES,
    DATA_RUNTIMES,
    DOMAIN,
)
from .entity import FSMEntity
from .models import FSMConfig
from .runtime import FSMRuntime
from .trigger_manager import TriggerManager

_LOGGER = logging.getLogger(__name__)


def prepare_hass_data(hass: HomeAssistant) -> None:
    """Ensure the integration data structure exists in hass.data."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_CONFIGS, {})
    hass.data[DOMAIN].setdefault(DATA_RUNTIMES, {})
    hass.data[DOMAIN].setdefault(DATA_ENTITIES, {})
    hass.data[DOMAIN].setdefault(DATA_PENDING_ENTITIES, [])


def register_fsm(
    hass: HomeAssistant,
    fsm_config: FSMConfig,
    *,
    from_yaml: bool,
) -> FSMEntity | None:
    """Create runtime objects and register a configured FSM."""
    prepare_hass_data(hass)

    if fsm_config.id in hass.data[DOMAIN][DATA_CONFIGS]:
        _LOGGER.error(
            "FSM with id '%s' is already configured; skipping%s",
            fsm_config.id,
            "" if from_yaml else " entry",
        )
        return None

    runtime = FSMRuntime(hass, fsm_config)
    entity = FSMEntity(runtime)
    trigger_manager = TriggerManager(hass, runtime)
    runtime.trigger_manager = trigger_manager

    hass.data[DOMAIN][DATA_CONFIGS][fsm_config.id] = fsm_config
    hass.data[DOMAIN][DATA_RUNTIMES][fsm_config.id] = runtime
    hass.data[DOMAIN][DATA_ENTITIES][fsm_config.id] = entity

    if from_yaml:
        hass.data[DOMAIN][DATA_PENDING_ENTITIES].append(entity)

    _LOGGER.debug(
        "Registered FSM '%s' with initial state '%s' (source=%s)",
        fsm_config.id,
        fsm_config.initial_state,
        "yaml" if from_yaml else "config_entry",
    )
    return entity


async def async_unregister_fsm(hass: HomeAssistant, fsm_id: str) -> None:
    prepare_hass_data(hass)

    runtime = hass.data[DOMAIN][DATA_RUNTIMES].pop(fsm_id, None)
    if runtime is not None and runtime.trigger_manager is not None:
        await runtime.trigger_manager.async_unload()

    entity = hass.data[DOMAIN][DATA_ENTITIES].pop(fsm_id, None)
    if entity is not None:
        pending_entities = hass.data[DOMAIN][DATA_PENDING_ENTITIES]
        if entity in pending_entities:
            pending_entities.remove(entity)

    hass.data[DOMAIN][DATA_CONFIGS].pop(fsm_id, None)


async def async_unload_all(hass: HomeAssistant) -> bool:
    prepare_hass_data(hass)

    for fsm_id in list(hass.data[DOMAIN][DATA_RUNTIMES].keys()):
        await async_unregister_fsm(hass, fsm_id)

    hass.data[DOMAIN][DATA_PENDING_ENTITIES].clear()
    return True
