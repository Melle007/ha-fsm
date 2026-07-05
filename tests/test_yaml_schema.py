from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.fsm.const import INTERNAL_STARTUP_TRIGGER_ID
from custom_components.fsm.yaml_schema import parse_fsm_config_item


def test_parse_fsm_config_item_rejects_duplicate_states() -> None:
    with pytest.raises(vol.Invalid, match="duplicate states"):
        parse_fsm_config_item(
            {
                "id": "test_fsm",
                "name": "Test FSM",
                "states": ["idle", "idle"],
                "initial_state": "idle",
                "restore_state": True,
                "evaluate_on_start": False,
                "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
                "transitions": [{"from": "idle", "to": "idle", "trigger_id": "go"}],
                "variables": {},
            }
        )


def test_parse_fsm_config_item_rejects_reserved_variable_names() -> None:
    with pytest.raises(vol.Invalid, match="reserved names"):
        parse_fsm_config_item(
            {
                "id": "test_fsm",
                "name": "Test FSM",
                "states": ["idle", "active"],
                "initial_state": "idle",
                "restore_state": True,
                "evaluate_on_start": False,
                "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
                "transitions": [{"from": "idle", "to": "active", "trigger_id": "go"}],
                "variables": {"trigger": "bad"},
            }
        )


def test_parse_fsm_config_item_valid_config_returns_fsm_config() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": ["idle", "active"],
            "initial_state": "idle",
            "restore_state": True,
            "evaluate_on_start": False,
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "transitions": [{"from": "idle", "to": "active", "trigger_id": "go"}],
            "variables": {"x": 1},
        }
    )

    assert config.id == "test_fsm"
    assert config.initial_state == "idle"
    assert config.debug is False
    assert len(config.transitions) == 1
    assert config.variables == {"x": 1}


def test_parse_fsm_config_item_accepts_debug_flag() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": ["idle", "active"],
            "initial_state": "idle",
            "debug": True,
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "transitions": [{"from": "idle", "to": "active", "trigger_id": "go"}],
            "variables": {},
        }
    )

    assert config.debug is True


def test_parse_fsm_config_item_allows_uuid_fsm_id() -> None:
    config = parse_fsm_config_item(
        {
            "id": "4fd1c835-51b7-4818-a626-44a202156825",
            "name": "Test FSM",
            "states": ["idle", "active"],
            "initial_state": "idle",
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "transitions": [{"from": "idle", "to": "active", "trigger_id": "go"}],
            "variables": {},
        }
    )

    assert config.id == "4fd1c835-51b7-4818-a626-44a202156825"


def test_parse_fsm_config_item_allows_wildcard_from_state() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": ["idle", "active"],
            "initial_state": "idle",
            "restore_state": True,
            "evaluate_on_start": False,
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "transitions": [{"from": "*", "to": "active", "trigger_id": "go"}],
            "variables": {},
        }
    )

    assert config.transitions[0].from_state == "*"


def test_parse_fsm_config_item_allows_internal_startup_trigger() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": ["idle", "active"],
            "initial_state": "idle",
            "restore_state": True,
            "evaluate_on_start": True,
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "transitions": [
                {
                    "from": "idle",
                    "to": "active",
                    "trigger_id": INTERNAL_STARTUP_TRIGGER_ID,
                }
            ],
            "variables": {},
        }
    )

    assert config.transitions[0].trigger_id == INTERNAL_STARTUP_TRIGGER_ID


def test_parse_fsm_config_item_accepts_state_centric_config() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": {
                "idle": {
                    "on": {
                        "go": [
                            {"to": "active", "guard": "{{ false }}"},
                            {"to": "fallback"},
                        ]
                    }
                },
                "active": None,
                "fallback": {},
            },
            "initial_state": "idle",
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "variables": {},
        }
    )

    assert config.states == ["idle", "active", "fallback"]
    assert [transition.to_state for transition in config.transitions] == [
        "active",
        "fallback",
    ]
    assert [transition.trigger_id for transition in config.transitions] == ["go", "go"]


def test_parse_fsm_config_item_accepts_yaml_boolean_on_key() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": {
                "idle": {True: {"go": {"to": "active"}}},
                "active": {},
            },
            "initial_state": "idle",
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "variables": {},
        }
    )

    assert len(config.transitions) == 1
    assert config.transitions[0].from_state == "idle"
    assert config.transitions[0].to_state == "active"


def test_parse_fsm_config_item_accepts_global_startup_handlers() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": {"idle": {}, "active": {}},
            "initial_state": "idle",
            "evaluate_on_start": True,
            "triggers": [{"id": "go", "platform": "event", "event_type": "go"}],
            "global": {
                "on": [
                    {
                        "trigger_id": INTERNAL_STARTUP_TRIGGER_ID,
                        "to": "active",
                    }
                ]
            },
            "variables": {},
        }
    )

    assert config.transitions[0].from_state == "*"
    assert config.transitions[0].trigger_id == INTERNAL_STARTUP_TRIGGER_ID


def test_parse_fsm_config_item_allows_duplicate_ha_trigger_ids() -> None:
    config = parse_fsm_config_item(
        {
            "id": "test_fsm",
            "name": "Test FSM",
            "states": {"idle": {"on": {"go": {"to": "active"}}}, "active": {}},
            "initial_state": "idle",
            "triggers": [
                {"id": "go", "platform": "state", "entity_id": "sensor.a"},
                {"id": "go", "platform": "state", "entity_id": "sensor.b"},
            ],
            "variables": {},
        }
    )

    assert [trigger.id for trigger in config.triggers] == ["go", "go"]
    assert config.transitions[0].trigger_id == "go"
