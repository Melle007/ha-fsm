"""Tests for the FSM manager (register / unregister / unload)."""

from __future__ import annotations

import pytest

from custom_components.fsm.const import (
    DATA_CONFIGS,
    DATA_ENTITIES,
    DATA_PENDING_ENTITIES,
    DATA_RUNTIMES,
    DOMAIN,
)
from custom_components.fsm.manager import (
    async_unregister_fsm,
    async_unload_all,
    prepare_hass_data,
    register_fsm,
)
from custom_components.fsm.models import FSMConfig, TriggerConfig, TransitionConfig


class _FakeBus:
    def async_fire(self, event_type, event_data, context=None):
        pass


class _FakeHass:
    def __init__(self):
        self.data = {}
        self.bus = _FakeBus()


def _config(fsm_id: str = "test_fsm") -> FSMConfig:
    return FSMConfig(
        id=fsm_id,
        name="Test FSM",
        states=["idle", "active"],
        initial_state="idle",
        restore_state=True,
        debug=False,
        triggers=[TriggerConfig(id="go", platform="event", config={})],
        transitions=[
            TransitionConfig(
                from_state="idle",
                to_state="active",
                trigger_id="go",
                id="idle_to_active",
            )
        ],
        variables={},
        evaluate_on_start=False,
    )


def test_register_fsm_creates_runtime_and_entity() -> None:
    hass = _FakeHass()

    entity = register_fsm(hass, _config(), from_yaml=False)

    assert entity is not None
    assert hass.data[DOMAIN][DATA_RUNTIMES]["test_fsm"] is not None
    assert hass.data[DOMAIN][DATA_ENTITIES]["test_fsm"] is entity
    assert hass.data[DOMAIN][DATA_CONFIGS]["test_fsm"].id == "test_fsm"
    # A config-entry (non-YAML) registration must not be pending.
    assert hass.data[DOMAIN][DATA_PENDING_ENTITIES] == []
    # The runtime is wired to a trigger manager by registration.
    assert hass.data[DOMAIN][DATA_RUNTIMES]["test_fsm"].trigger_manager is not None


def test_register_fsm_from_yaml_appends_pending_entity() -> None:
    hass = _FakeHass()

    entity = register_fsm(hass, _config("yaml_fsm"), from_yaml=True)

    assert entity is not None
    assert hass.data[DOMAIN][DATA_PENDING_ENTITIES] == [entity]


def test_register_fsm_rejects_duplicate_id() -> None:
    hass = _FakeHass()
    first = register_fsm(hass, _config(), from_yaml=False)

    second = register_fsm(hass, _config(), from_yaml=False)

    assert second is None
    assert first is not None
    assert len(hass.data[DOMAIN][DATA_RUNTIMES]) == 1


@pytest.mark.asyncio
async def test_unregister_fsm_clears_all_registration_state() -> None:
    hass = _FakeHass()
    entity = register_fsm(hass, _config(), from_yaml=True)

    await async_unregister_fsm(hass, "test_fsm")

    assert hass.data[DOMAIN][DATA_RUNTIMES].get("test_fsm") is None
    assert hass.data[DOMAIN][DATA_ENTITIES].get("test_fsm") is None
    assert hass.data[DOMAIN][DATA_CONFIGS].get("test_fsm") is None
    assert entity not in hass.data[DOMAIN][DATA_PENDING_ENTITIES]


@pytest.mark.asyncio
async def test_unregister_unknown_fsm_is_a_noop() -> None:
    hass = _FakeHass()
    register_fsm(hass, _config(), from_yaml=False)

    await async_unregister_fsm(hass, "does_not_exist")

    # The registered FSM is untouched.
    assert hass.data[DOMAIN][DATA_RUNTIMES].get("test_fsm") is not None


@pytest.mark.asyncio
async def test_unload_all_clears_every_registered_fsm() -> None:
    hass = _FakeHass()
    register_fsm(hass, _config("fsm_a"), from_yaml=True)
    register_fsm(hass, _config("fsm_b"), from_yaml=False)

    result = await async_unload_all(hass)

    assert result is True
    assert hass.data[DOMAIN][DATA_RUNTIMES] == {}
    assert hass.data[DOMAIN][DATA_ENTITIES] == {}
    assert hass.data[DOMAIN][DATA_CONFIGS] == {}
    assert hass.data[DOMAIN][DATA_PENDING_ENTITIES] == []


def test_prepare_hass_data_is_idempotent() -> None:
    hass = _FakeHass()
    prepare_hass_data(hass)
    hass.data[DOMAIN][DATA_RUNTIMES]["sentinel"] = object()

    prepare_hass_data(hass)

    # Existing data must survive a second call.
    assert "sentinel" in hass.data[DOMAIN][DATA_RUNTIMES]
