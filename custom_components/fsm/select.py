"""Select platform exposure for FSM entities."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENTRY_DATA_FSM_CONFIG, CONF_ID, DATA_ENTITIES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FSM select entities from config entry."""
    fsm_dict = entry.data[CONF_ENTRY_DATA_FSM_CONFIG]
    fsm_id = fsm_dict[CONF_ID]

    domain_data = hass.data.get(DOMAIN, {})
    entity = domain_data.get(DATA_ENTITIES, {}).get(fsm_id)

    if entity is not None:
        async_add_entities([entity])
    else:
        _LOGGER.warning("No FSM entity found for id '%s'", fsm_id)