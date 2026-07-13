from __future__ import annotations

from homeassistant import config_entries, data_entry_flow

from .const import CONF_ENTRY_DATA_FSM_CONFIG, CONF_ID, CONF_NAME, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class FSMConfigFlow(config_entries.ConfigFlow):
    """Config flow for the FSM integration. YAML-first; import-only for config entries."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> data_entry_flow.FlowResult:
        """Inform the user that this is a YAML-first integration."""
        return self.async_abort(reason="yaml_only")

    async def async_step_import(
        self, import_data: dict | None = None
    ) -> data_entry_flow.FlowResult:
        """Import YAML config into a config entry."""
        await self.async_set_unique_id(import_data[CONF_ID])
        result = self._abort_if_unique_id_configured(
            updates={CONF_ENTRY_DATA_FSM_CONFIG: import_data}
        )
        if result is not None:
            return result

        return self.async_create_entry(
            title=import_data[CONF_NAME],
            data={CONF_ENTRY_DATA_FSM_CONFIG: import_data},
        )