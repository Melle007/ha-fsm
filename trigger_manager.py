from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger import async_initialize_triggers

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TriggerManager:
    def __init__(self, hass: HomeAssistant, runtime) -> None:
        self.hass = hass
        self.runtime = runtime
        self._remove_triggers: list[CALLBACK_TYPE] = []

    def _normalize_trigger_config(self, trigger_config: dict[str, Any]) -> dict[str, Any]:
        """Normalize trigger config before passing it to Home Assistant."""
        normalized = dict(trigger_config)

        if (
            normalized.get("platform") == "template"
            and isinstance(normalized.get("value_template"), str)
        ):
            normalized["value_template"] = Template(
                normalized["value_template"],
                self.hass,
            )

        if "entity_id" in normalized and isinstance(normalized["entity_id"], str):
            normalized["entity_id"] = [normalized["entity_id"]]

        if "entity_ids" in normalized and isinstance(normalized["entity_ids"], str):
            normalized["entity_ids"] = [normalized["entity_ids"]]

        return normalized

    async def async_setup(self) -> None:
        success_count = 0
        failure_count = 0
        errors: list[str] = []

        for trig in self.runtime.config.triggers:
            try:
                trigger_config = self._normalize_trigger_config(
                    {
                        "platform": trig.platform,
                        "id": trig.id,
                        **trig.config,
                    }
                )

                if trigger_config["platform"] == "event":
                    remove = self._attach_event_trigger(trigger_config)
                    self._remove_triggers.append(remove)
                    success_count += 1
                    continue

                remove = await self._attach_ha_trigger(trigger_config, trig.id)
                self._remove_triggers.append(remove)
                success_count += 1

            except Exception as err:
                failure_count += 1
                errors.append(
                    (
                        f"{trig.id}: {err} "
                        f"(platform={trig.platform}, fsm_id={self.runtime.config.id})"
                    )
                )
                _LOGGER.exception(
                    "Failed to attach trigger '%s' for FSM '%s'",
                    trig.id,
                    self.runtime.config.id,
                )

        self.runtime.notify_trigger_setup_result(
            success_count,
            failure_count,
            errors,
            complete=True,
        )

    async def _attach_ha_trigger(
        self,
        trigger_config: dict[str, Any],
        configured_trigger_id: str,
    ) -> CALLBACK_TYPE:
        """Attach a non-event trigger via Home Assistant's trigger helper."""

        async def _handle_trigger(
            run_variables: dict[str, Any],
            context: Context | None = None,
        ) -> None:
            trigger = dict(run_variables.get("trigger", {}))

            trigger_id = trigger.get("id") or configured_trigger_id
            trigger["id"] = trigger_id

            payload = {
                **run_variables,
                "trigger": trigger,
            }

            await self.runtime.async_handle_trigger(
                trigger_id,
                payload,
                context,
            )

        return await async_initialize_triggers(
            self.hass,
            [trigger_config],
            _handle_trigger,
            DOMAIN,
            self.runtime.config.name,
            log_cb=_LOGGER.log,
        )

    def _attach_event_trigger(self, trigger_config: dict[str, Any]) -> CALLBACK_TYPE:
        """Attach an event trigger directly to the Home Assistant event bus."""
        event_type = trigger_config["event_type"]
        trigger_id = trigger_config["id"]
        expected_event_data = trigger_config.get("event_data")

        @callback
        def _event_listener(event: Event) -> None:
            if expected_event_data is not None and not self._event_data_matches(
                event.data,
                expected_event_data,
            ):
                return

            self.hass.async_create_task(
                self.runtime.async_handle_trigger(
                    trigger_id,
                    {
                        "trigger": {
                            "id": trigger_id,
                            "platform": "event",
                            "event_type": event.event_type,
                            "event": event,
                            "event_data": event.data,
                            "description": f"event '{event.event_type}'",
                        }
                    },
                    event.context,
                )
            )

        return self.hass.bus.async_listen(event_type, _event_listener)

    @staticmethod
    def _event_data_matches(
        actual_event_data: dict[str, Any],
        expected_event_data: dict[str, Any],
    ) -> bool:
        """Return true if all expected event data keys match the actual event data."""
        return all(
            actual_event_data.get(key) == expected_value
            for key, expected_value in expected_event_data.items()
        )

    async def async_unload(self) -> None:
        """Unload all attached triggers."""
        while self._remove_triggers:
            remove = self._remove_triggers.pop()
            try:
                remove()
            except Exception:
                _LOGGER.exception(
                    "Failed to unload trigger callback for FSM '%s'",
                    self.runtime.config.id,
                )
