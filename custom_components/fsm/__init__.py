from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .const import CONF_FSM, DOMAIN, PLATFORM_SELECT
from .manager import async_unload_all, prepare_hass_data, register_fsm
from .services import async_register_services
from .yaml_schema import parse_fsm_configs

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    prepare_hass_data(hass)
    await async_register_services(hass)

    if CONF_FSM not in config:
        return True

    created_fsm_ids: list[str] = []

    try:
        fsm_configs = parse_fsm_configs(config)
        for fsm_config in fsm_configs:
            entity = register_fsm(hass, fsm_config, from_yaml=True)
            if entity is not None:
                created_fsm_ids.append(fsm_config.id)
    except Exception:
        _LOGGER.exception("Failed to set up YAML FSM configuration")
        await async_unload_all(hass)
        return False

    if not created_fsm_ids:
        return True

    await discovery.async_load_platform(
        hass, PLATFORM_SELECT, DOMAIN, {}, config
    )

    return True


async def async_unload(hass: HomeAssistant) -> bool:
    return await async_unload_all(hass)
