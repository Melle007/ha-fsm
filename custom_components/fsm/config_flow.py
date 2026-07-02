from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class FSMConfigFlow(config_entries.ConfigFlow):
    """Reject user-created config entries with an explicit YAML-first message."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_abort(reason="This integration is configured via YAML only.")
