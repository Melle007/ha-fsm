"""Select platform exposure for FSM entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ID, DATA_ENTITIES, DATA_PENDING_ENTITIES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up YAML-configured FSM select entities."""
    domain_data = hass.data.get(DOMAIN, {})
    pending_entities = domain_data.get(DATA_PENDING_ENTITIES, [])

    if pending_entities:
        _LOGGER.debug("Adding pending FSM entities: %s", pending_entities)
        async_add_entities(list(pending_entities))
        pending_entities.clear()
    else:
        _LOGGER.warning("No pending FSM entities found during select setup")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FSM select entities from config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    entity_id = entry.data.get(CONF_ID)

    if not entity_id:
        return

    entity = domain_data.get(DATA_ENTITIES, {}).get(entity_id)
    if entity is not None:
        async_add_entities([entity])
