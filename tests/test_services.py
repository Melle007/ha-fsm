"""Tests for FSM service registration and handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.fsm.const import (
    DATA_RUNTIMES,
    DOMAIN,
    SERVICE_SET_STATE,
    SERVICE_TRIGGER,
)
from custom_components.fsm.exceptions import FSMRuntimeError
from custom_components.fsm.services import async_register_services


class _FakeServices:
    def __init__(self) -> None:
        self.registered: dict[tuple[str, str], tuple] = {}
        self.calls: list[tuple[str, str]] = []

    def has_service(self, domain: str, service: str) -> bool:
        return (domain, service) in self.registered

    def async_register(self, domain, service, handler, schema=None) -> None:
        self.registered[(domain, service)] = (handler, schema)
        self.calls.append((domain, service))


class _FakeHass:
    def __init__(self, runtimes: dict) -> None:
        self.data = {DOMAIN: {DATA_RUNTIMES: runtimes}}
        self.services = _FakeServices()


def _make_runtime(fsm_id: str = "fsm_a", entity_id: str = "select.fsm_a"):
    return SimpleNamespace(
        entity=SimpleNamespace(entity_id=entity_id),
        async_handle_trigger=AsyncMock(),
        async_force_state=AsyncMock(),
    )


def _call(data: dict) -> SimpleNamespace:
    return SimpleNamespace(data=data, context=None)


def _trigger_handler(hass: _FakeHass):
    return hass.services.registered[(DOMAIN, SERVICE_TRIGGER)][0]


def _set_state_handler(hass: _FakeHass):
    return hass.services.registered[(DOMAIN, SERVICE_SET_STATE)][0]


@pytest.mark.asyncio
async def test_register_services_registers_both_with_schemas() -> None:
    hass = _FakeHass({})

    await async_register_services(hass)

    assert (DOMAIN, SERVICE_TRIGGER) in hass.services.registered
    assert (DOMAIN, SERVICE_SET_STATE) in hass.services.registered
    # Each registration carries a voluptuous schema.
    assert hass.services.registered[(DOMAIN, SERVICE_TRIGGER)][1] is not None
    assert hass.services.registered[(DOMAIN, SERVICE_SET_STATE)][1] is not None


@pytest.mark.asyncio
async def test_register_services_is_idempotent() -> None:
    hass = _FakeHass({})

    await async_register_services(hass)
    await async_register_services(hass)

    # Registered once per service; the second call must be a no-op.
    assert len(hass.services.calls) == 2


@pytest.mark.asyncio
async def test_trigger_resolves_by_fsm_id() -> None:
    runtime = _make_runtime()
    hass = _FakeHass({"fsm_a": runtime})
    await async_register_services(hass)

    await _trigger_handler(hass)(_call({"fsm_id": "fsm_a", "trigger_id": "go"}))

    runtime.async_handle_trigger.assert_awaited_once_with("go", {"service": True}, None)


@pytest.mark.asyncio
async def test_trigger_resolves_by_entity_id() -> None:
    runtime = _make_runtime()
    hass = _FakeHass({"fsm_a": runtime})
    await async_register_services(hass)

    await _trigger_handler(hass)(_call({"entity_id": "select.fsm_a", "trigger_id": "go"}))

    runtime.async_handle_trigger.assert_awaited_once_with("go", {"service": True}, None)


@pytest.mark.asyncio
async def test_trigger_accepts_matching_fsm_id_and_entity_id() -> None:
    runtime = _make_runtime()
    hass = _FakeHass({"fsm_a": runtime})
    await async_register_services(hass)

    await _trigger_handler(hass)(
        _call({"fsm_id": "fsm_a", "entity_id": "select.fsm_a", "trigger_id": "go"})
    )

    runtime.async_handle_trigger.assert_awaited_once_with("go", {"service": True}, None)


@pytest.mark.asyncio
async def test_trigger_rejects_conflicting_target() -> None:
    runtime = _make_runtime()
    hass = _FakeHass({"fsm_a": runtime})
    await async_register_services(hass)

    with pytest.raises(ServiceValidationError, match="does not match"):
        await _trigger_handler(hass)(
            _call({"fsm_id": "fsm_a", "entity_id": "select.other", "trigger_id": "go"})
        )


@pytest.mark.asyncio
async def test_trigger_rejects_unknown_fsm_id() -> None:
    hass = _FakeHass({})
    await async_register_services(hass)

    with pytest.raises(ServiceValidationError, match="Unknown FSM id"):
        await _trigger_handler(hass)(_call({"fsm_id": "nope", "trigger_id": "go"}))


@pytest.mark.asyncio
async def test_trigger_rejects_unknown_entity_id() -> None:
    hass = _FakeHass({})
    await async_register_services(hass)

    with pytest.raises(ServiceValidationError, match="Unknown FSM entity_id"):
        await _trigger_handler(hass)(
            _call({"entity_id": "select.nope", "trigger_id": "go"})
        )


@pytest.mark.asyncio
async def test_trigger_requires_a_target() -> None:
    hass = _FakeHass({})
    await async_register_services(hass)

    with pytest.raises(ServiceValidationError, match="Either fsm_id or entity_id"):
        await _trigger_handler(hass)(_call({"trigger_id": "go"}))


@pytest.mark.asyncio
async def test_set_state_forces_state() -> None:
    runtime = _make_runtime()
    hass = _FakeHass({"fsm_a": runtime})
    await async_register_services(hass)

    await _set_state_handler(hass)(_call({"fsm_id": "fsm_a", "state": "active"}))

    runtime.async_force_state.assert_awaited_once_with("active")


@pytest.mark.asyncio
async def test_set_state_wraps_runtime_error() -> None:
    runtime = _make_runtime()
    runtime.async_force_state = AsyncMock(
        side_effect=FSMRuntimeError("Invalid state 'bad' for FSM 'fsm_a'")
    )
    hass = _FakeHass({"fsm_a": runtime})
    await async_register_services(hass)

    with pytest.raises(ServiceValidationError):
        await _set_state_handler(hass)(_call({"fsm_id": "fsm_a", "state": "bad"}))
