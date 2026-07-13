from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .action_validation import normalize_action_item, normalize_actions
from .const import (
    CONF_ACTIONS,
    CONF_DEBUG,
    CONF_EVALUATE_ON_START,
    CONF_FSM,
    CONF_FROM,
    CONF_GLOBAL,
    CONF_GUARD,
    CONF_ID,
    CONF_INITIAL_STATE,
    CONF_NAME,
    CONF_ON,
    CONF_PLATFORM,
    CONF_RESTORE_STATE,
    CONF_STATES,
    CONF_TO,
    CONF_TRANSITIONS,
    CONF_TRIGGER_ID,
    CONF_TRIGGERS,
    CONF_VARIABLES,
    INTERNAL_STARTUP_TRIGGER_ID,
    RESERVED_VARIABLE_NAMES,
)
from .models import FSMConfig, TransitionConfig, TriggerConfig


_LOGGER = logging.getLogger(__name__)


def _validate_action_item(value: Any) -> dict[str, Any]:
    try:
        return normalize_action_item(value)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _validate_actions_for_runtime(actions: list[Any]) -> list[dict[str, Any]]:
    try:
        return normalize_actions(actions)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _trigger_schema(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise vol.Invalid("Trigger must be a mapping")

    if CONF_ID not in value:
        raise vol.Invalid("Trigger requires 'id'")

    if CONF_PLATFORM not in value:
        raise vol.Invalid("Trigger requires 'platform'")

    return value


FSM_YAML_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FSM): [
            {
                vol.Required(CONF_ID): cv.string,
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_STATES): vol.Any(
                    vol.All([cv.string], vol.Length(min=1)),
                    vol.All(dict, vol.Length(min=1)),
                ),
                vol.Required(CONF_INITIAL_STATE): cv.string,
                vol.Optional(CONF_RESTORE_STATE, default=True): cv.boolean,
                vol.Optional(CONF_DEBUG, default=False): cv.boolean,
                vol.Optional(CONF_EVALUATE_ON_START, default=False): cv.boolean,
                vol.Required(CONF_TRIGGERS): vol.All(
                    [_trigger_schema], vol.Length(min=1)
                ),
                vol.Optional(CONF_TRANSITIONS, default=[]): vol.All(
                    [
                        {
                            vol.Required(CONF_FROM): vol.Any(
                                cv.string,
                                vol.All([cv.string], vol.Length(min=1)),
                            ),
                            vol.Required(CONF_TO): cv.string,
                            vol.Required(CONF_TRIGGER_ID): vol.Any(
                                cv.string,
                                vol.All([cv.string], vol.Length(min=1)),
                            ),
                            vol.Optional(CONF_GUARD): cv.string,
                            vol.Optional(CONF_ACTIONS, default=[]): vol.All(
                                list,
                                [_validate_action_item],
                            ),
                        }
                    ],
                ),
                vol.Optional(CONF_VARIABLES, default={}): dict,
                vol.Optional(CONF_GLOBAL, default={}): dict,
            }
        ]
    },
    extra=vol.ALLOW_EXTRA,
)


def _state_names(raw_states: Any) -> list[str]:
    if isinstance(raw_states, dict):
        state_keys = list(raw_states)
        non_string_keys = [k for k in state_keys if not isinstance(k, str)]
        if non_string_keys:
            raise vol.Invalid(
                f"FSM state names must be strings. "
                f"YAML may have coerced '{non_string_keys[0]}' (e.g. 'ON' or 'OFF' as a YAML keyword). "
                f"Quote your state names: \"ON\"."
            )
        return state_keys
    return list(raw_states)


def _get_on_handlers(raw_config: dict[str, Any]) -> Any:
    # 1. Standard: quoted "on" im YAML
    if CONF_ON in raw_config:
        return raw_config[CONF_ON]
    # 2. YAML-Boolean True (vor JSON-Roundtrip)
    if True in raw_config:
        return raw_config[True]
    # 3. Nach JSON-Roundtrip: True → "true"
    if "true" in raw_config:
        return raw_config["true"]
    # 4. Failsafe für andere Serialisierungen
    if "True" in raw_config:
        return raw_config["True"]
    return None


def _normalize_on_handlers(
    fsm_id: str,
    source_state: str,
    raw_on: Any,
) -> list[dict[str, Any]]:
    if raw_on is None:
        return []

    handlers: list[dict[str, Any]] = []
    if isinstance(raw_on, list):
        for handler in raw_on:
            if not isinstance(handler, dict):
                raise vol.Invalid(
                    f"FSM '{fsm_id}': state '{source_state}' on handlers must be mappings"
                )
            handlers.append(handler)
        return handlers

    if isinstance(raw_on, dict):
        for trigger_id, candidates in raw_on.items():
            candidate_list = candidates if isinstance(candidates, list) else [candidates]
            for candidate in candidate_list:
                if not isinstance(candidate, dict):
                    raise vol.Invalid(
                        f"FSM '{fsm_id}': state '{source_state}' trigger '{trigger_id}' handlers must be mappings"
                    )
                handlers.append({CONF_TRIGGER_ID: trigger_id, **candidate})
        return handlers

    raise vol.Invalid(f"FSM '{fsm_id}': state '{source_state}' on must be a list or mapping")


def _parse_state_centric_transitions(
    item: dict[str, Any],
    states: list[str],
    trigger_ids: set[str],
) -> list[TransitionConfig]:
    transitions: list[TransitionConfig] = []

    def add_handlers(source_state: str, raw_on: Any) -> None:
        for handler in _normalize_on_handlers(item[CONF_ID], source_state, raw_on):
            if CONF_TO not in handler:
                raise vol.Invalid(
                    f"FSM '{item[CONF_ID]}': transition from '{source_state}' requires 'to'"
                )

            raw_trigger_ids = handler.get(CONF_TRIGGER_ID)
            if raw_trigger_ids is None:
                raise vol.Invalid(
                    f"FSM '{item[CONF_ID]}': transition from '{source_state}' requires 'trigger_id'"
                )
            trigger_ids_for_transition = (
                [raw_trigger_ids]
                if isinstance(raw_trigger_ids, str)
                else list(raw_trigger_ids)
            )

            if handler[CONF_TO] not in states:
                raise vol.Invalid(
                    f"FSM '{item[CONF_ID]}': transition to '{handler[CONF_TO]}' not in states"
                )

            for trigger_id in trigger_ids_for_transition:
                if (
                    trigger_id != INTERNAL_STARTUP_TRIGGER_ID
                    and trigger_id not in trigger_ids
                ):
                    raise vol.Invalid(
                        f"FSM '{item[CONF_ID]}': transition trigger_id '{trigger_id}' not defined"
                    )

                transitions.append(
                    TransitionConfig(
                        from_state=source_state,
                        to_state=handler[CONF_TO],
                        trigger_id=trigger_id,
                        guard=handler.get(CONF_GUARD),
                        actions=_validate_actions_for_runtime(
                            handler.get(CONF_ACTIONS, [])
                        ),
                        id=(
                            f"{item[CONF_ID]}__{source_state}__"
                            f"{trigger_id}__{handler[CONF_TO]}__{len(transitions)}"
                        ),
                    )
                )

    raw_states = item[CONF_STATES]
    if isinstance(raw_states, dict):
        for state_name, state_config in raw_states.items():
            if state_config is None:
                continue
            if not isinstance(state_config, dict):
                raise vol.Invalid(
                    f"FSM '{item[CONF_ID]}': state '{state_name}' must be a mapping"
                )
            add_handlers(state_name, _get_on_handlers(state_config))

    raw_global = item.get(CONF_GLOBAL) or {}
    if raw_global:
        if not isinstance(raw_global, dict):
            raise vol.Invalid(f"FSM '{item[CONF_ID]}': global must be a mapping")
        add_handlers("*", _get_on_handlers(raw_global))

    return transitions


def _parse_fsm_item(item: dict[str, Any]) -> FSMConfig:
    states = _state_names(item[CONF_STATES])
    initial_state = item[CONF_INITIAL_STATE]

    duplicate_states = sorted({state for state in states if states.count(state) > 1})
    if duplicate_states:
        raise vol.Invalid(
            f"FSM '{item[CONF_ID]}': duplicate states not allowed: {', '.join(duplicate_states)}"
        )

    if initial_state not in states:
        msg = f"FSM '{item[CONF_ID]}': initial_state '{initial_state}' not in states"
        if initial_state in ("True", "False"):
            msg += (
                f". Did you accidentally use a YAML boolean? "
                f"Use a valid state name like '{states[0]}'."
            )
        msg += f" Available states: {', '.join(states)}"
        raise vol.Invalid(msg)

    trigger_ids: set[str] = set()
    triggers: list[TriggerConfig] = []

    for trig in item[CONF_TRIGGERS]:
        trig_id = trig[CONF_ID]
        trigger_ids.add(trig_id)
        platform = trig[CONF_PLATFORM]
        trigger_config = {
            key: value
            for key, value in trig.items()
            if key not in (CONF_ID, CONF_PLATFORM)
        }
        triggers.append(
            TriggerConfig(
                id=trig_id,
                platform=platform,
                config=trigger_config,
            )
        )

    transitions = _parse_state_centric_transitions(item, states, trigger_ids)

    for tr in item.get(CONF_TRANSITIONS, []):
        from_states = [tr[CONF_FROM]] if isinstance(tr[CONF_FROM], str) else tr[CONF_FROM]
        trigger_ids_for_transition = (
            [tr[CONF_TRIGGER_ID]]
            if isinstance(tr[CONF_TRIGGER_ID], str)
            else tr[CONF_TRIGGER_ID]
        )

        for from_state in from_states:
            if from_state != "*" and from_state not in states:
                raise vol.Invalid(
                    f"FSM '{item[CONF_ID]}': transition from '{from_state}' not in states"
                )

            if tr[CONF_TO] not in states:
                raise vol.Invalid(
                    f"FSM '{item[CONF_ID]}': transition to '{tr[CONF_TO]}' not in states"
                )

            for trigger_id in trigger_ids_for_transition:
                if (
                    trigger_id != INTERNAL_STARTUP_TRIGGER_ID
                    and trigger_id not in trigger_ids
                ):
                    raise vol.Invalid(
                        f"FSM '{item[CONF_ID]}': transition trigger_id '{trigger_id}' not defined"
                    )

                transitions.append(
                    TransitionConfig(
                        from_state=from_state,
                        to_state=tr[CONF_TO],
                        trigger_id=trigger_id,
                        guard=tr.get(CONF_GUARD),
                        actions=_validate_actions_for_runtime(
                            tr.get(CONF_ACTIONS, [])
                        ),
                        id=(
                            f"{item[CONF_ID]}__{from_state}__"
                            f"{trigger_id}__{tr[CONF_TO]}__{len(transitions)}"
                        ),
                    )
                )

    if not transitions:
        raise vol.Invalid(f"FSM '{item[CONF_ID]}': at least one transition is required")

    variables = item.get(CONF_VARIABLES, {})
    if variables is None:
        variables = {}

    if not isinstance(variables, dict):
        raise vol.Invalid(
            f"FSM '{item[CONF_ID]}': '{CONF_VARIABLES}' must be a mapping"
        )

    reserved_collisions = sorted(
        variable_name
        for variable_name in variables
        if variable_name in RESERVED_VARIABLE_NAMES
    )
    if reserved_collisions:
        raise vol.Invalid(
            f"FSM '{item[CONF_ID]}': variables use reserved names: {', '.join(reserved_collisions)}"
        )

    return FSMConfig(
        id=item[CONF_ID],
        name=item[CONF_NAME],
        states=states,
        initial_state=initial_state,
        restore_state=item[CONF_RESTORE_STATE],
        debug=item[CONF_DEBUG],
        triggers=triggers,
        transitions=transitions,
        variables=variables,
        evaluate_on_start=item[CONF_EVALUATE_ON_START],
    )


def parse_fsm_configs(raw_config: dict[str, Any]) -> list[FSMConfig]:
    cfg = FSM_YAML_SCHEMA(raw_config)
    results: list[FSMConfig] = []
    for item in cfg[CONF_FSM]:
        try:
            results.append(parse_fsm_config_item(item))
        except vol.Invalid as err:
            fsm_id = item.get(CONF_ID, "<unknown>")
            _LOGGER.warning("Skipping FSM '%s': %s", fsm_id, err)
    if not results:
        _LOGGER.warning("No valid FSM configurations found")
    return results


def parse_fsm_config_item(item: dict[str, Any]) -> FSMConfig:
    cfg = FSM_YAML_SCHEMA({CONF_FSM: [item]})
    return _parse_fsm_item(cfg[CONF_FSM][0])
