from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENTRY_DATA_FSM_CONFIG,
    CONF_FSM,
    CONF_ID,
    DATA_CONFIGS,
    DOMAIN,
    PLATFORM_SELECT,
)
from .manager import (
    async_unregister_fsm,
    async_unload_all,
    prepare_hass_data,
    register_fsm,
)
from .services import async_register_services
from .yaml_schema import FSM_YAML_SCHEMA, parse_fsm_config_item

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [PLATFORM_SELECT]

CONFIG_SCHEMA = FSM_YAML_SCHEMA


async def _async_update_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload an FSM when its imported YAML config changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_import_config(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> None:
    """Import YAML FSM configs into config entries after startup."""
    for fsm_dict in config[CONF_FSM]:
        fsm_id = fsm_dict.get(CONF_ID, "<unknown>")
        _LOGGER.debug("Initiating deferred import flow for FSM '%s'", fsm_id)
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=fsm_dict,
        )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the FSM integration."""
    prepare_hass_data(hass)
    await async_register_services(hass)

    # Remove config entries for FSMs that have been deleted from YAML.
    # These are "orphan" entries that would otherwise persist as entities.
    current_fsm_ids = {
        item[CONF_ID] for item in config.get(CONF_FSM, [])
    }
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id not in current_fsm_ids:
            _LOGGER.info(
                "Removing orphaned config entry for FSM '%s' (no longer in YAML)",
                entry.unique_id,
            )
            await hass.config_entries.async_remove(entry.entry_id)

    if CONF_FSM not in config:
        return True

    # Defer config entry creation to avoid deadlock during async_setup.
    # This is standard HA pattern for YAML-to-config-entry imports.
    hass.async_create_task(
        _async_import_config(hass, config),
        eager_start=True,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FSM from a config entry (created via YAML import)."""
    fsm_dict = entry.data[CONF_ENTRY_DATA_FSM_CONFIG]
    fsm_id = fsm_dict[CONF_ID]

    _LOGGER.debug("async_setup_entry for FSM '%s'", fsm_id)

    # YAML updates are handled by the config-entry update listener, which first
    # unloads the working entry and then performs a clean setup. Never tear down
    # an active runtime from inside setup; a duplicate setup attempt must leave
    # the working FSM intact.
    if fsm_id in hass.data[DOMAIN][DATA_CONFIGS]:
        _LOGGER.error("FSM '%s' is already active; refusing duplicate setup", fsm_id)
        return False

    try:
        fsm_config = parse_fsm_config_item(fsm_dict)
    except Exception:
        _LOGGER.exception("Failed to parse FSM config for entry '%s'", entry.entry_id)
        return False

    try:
        entity = register_fsm(hass, fsm_config, from_yaml=False)
    except Exception:
        _LOGGER.exception("Failed to register FSM '%s' from config entry", fsm_config.id)
        return False

    if entity is None:
        return False

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await async_unregister_fsm(hass, fsm_id)
        raise

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    fsm_dict = entry.data[CONF_ENTRY_DATA_FSM_CONFIG]
    fsm_id = fsm_dict[CONF_ID]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_unregister_fsm(hass, fsm_id)
    return unload_ok


async def async_unload(hass: HomeAssistant) -> bool:
    """Unload the integration entirely."""
    return await async_unload_all(hass)
