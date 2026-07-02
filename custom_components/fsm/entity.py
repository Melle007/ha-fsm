from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_AVAILABLE_TRIGGER_IDS,
    ATTR_CANDIDATE_TRANSITIONS,
    ATTR_CURRENT_STATE,
    ATTR_FSM_ID,
    ATTR_INITIAL_STATE,
    ATTR_INITIALIZED,
    ATTR_LAST_ACTION_ERROR,
    ATTR_LAST_ERROR,
    ATTR_LAST_TRANSITION,
    ATTR_LAST_TRANSITION_AT,
    ATTR_LAST_TRIGGER_ID,
    ATTR_MATCH_PRECEDENCE,
    ATTR_PREVIOUS_STATE,
    ATTR_READY,
    ATTR_RESTORED,
    ATTR_STATES,
    ATTR_TRANSITION_COUNT,
    ATTR_TRANSITIONS_SUMMARY,
    ATTR_TRIGGER_ATTACH_ERRORS,
    ATTR_TRIGGER_ATTACH_FAILURE_COUNT,
    ATTR_TRIGGER_ATTACH_SUCCESS_COUNT,
    ATTR_TRIGGER_SETUP_COMPLETE,
    ATTR_TRIGGER_SETUP_OK,
    DOMAIN,
)

if TYPE_CHECKING:
    from .runtime import FSMRuntime


class FSMEntity(SelectEntity, RestoreEntity):
    _attr_should_poll = False
    _attr_icon = "mdi:state-machine"

    def __init__(self, runtime: FSMRuntime) -> None:
        self.runtime = runtime
        self._attr_name = runtime.config.name
        self._attr_unique_id = f"{DOMAIN}_{runtime.config.id}"

    @property
    def current_option(self) -> str:
        return self.runtime.state

    @property
    def options(self) -> list[str]:
        return self.runtime.config.states

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_FSM_ID: self.runtime.config.id,
            ATTR_STATES: self.runtime.config.states,
            ATTR_INITIAL_STATE: self.runtime.config.initial_state,
            ATTR_CURRENT_STATE: self.runtime.state,
            ATTR_PREVIOUS_STATE: self.runtime.previous_state,
            ATTR_LAST_TRIGGER_ID: self.runtime.last_trigger_id,
            ATTR_LAST_TRANSITION: self.runtime.last_transition,
            ATTR_LAST_TRANSITION_AT: self.runtime.last_transition_at.isoformat()
            if isinstance(self.runtime.last_transition_at, datetime)
            else None,
            ATTR_TRANSITION_COUNT: self.runtime.transition_count,
            ATTR_TRANSITIONS_SUMMARY: self.runtime.transitions_summary,
            ATTR_AVAILABLE_TRIGGER_IDS: self.runtime.available_trigger_ids,
            ATTR_CANDIDATE_TRANSITIONS: self.runtime.candidate_transitions,
            ATTR_READY: self.runtime.ready,
            ATTR_INITIALIZED: self.runtime.initialized,
            ATTR_TRIGGER_SETUP_COMPLETE: self.runtime.trigger_setup_complete,
            ATTR_TRIGGER_SETUP_OK: self.runtime.trigger_setup_ok,
            ATTR_MATCH_PRECEDENCE: self.runtime.match_precedence,
            ATTR_RESTORED: self.runtime.restored,
            ATTR_LAST_ERROR: self.runtime.last_error,
            ATTR_LAST_ACTION_ERROR: self.runtime.last_action_error,
            ATTR_TRIGGER_ATTACH_SUCCESS_COUNT: self.runtime.trigger_attach_success_count,
            ATTR_TRIGGER_ATTACH_FAILURE_COUNT: self.runtime.trigger_attach_failure_count,
            ATTR_TRIGGER_ATTACH_ERRORS: self.runtime.trigger_attach_errors,
        }

    async def async_select_option(self, option: str) -> None:
        await self.runtime.async_force_state(option)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.runtime.entity = self

        if not self.runtime.config.restore_state:
            await self.runtime.async_initialize(None)
        else:
            last_state = await self.async_get_last_state()
            restored = last_state.state if last_state is not None else None
            await self.runtime.async_initialize(restored)

        if self.runtime.trigger_manager is not None:
            await self.runtime.trigger_manager.async_setup()

        if self.runtime.config.evaluate_on_start:
            await self.runtime.async_evaluate_startup()
