"""Tests for config-entry lifecycle behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryError

from custom_components.fsm import (
    _async_update_listener,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.fsm.const import (
    CONF_ENTRY_DATA_FSM_CONFIG,
    CONF_FSM,
    CONF_ID,
    DATA_CONFIGS,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_update_listener_reloads_entry() -> None:
    config_entries = SimpleNamespace(async_reload=AsyncMock())
    hass = SimpleNamespace(config_entries=config_entries)
    entry = SimpleNamespace(entry_id="entry-id")

    await _async_update_listener(hass, entry)

    config_entries.async_reload.assert_awaited_once_with("entry-id")


@pytest.mark.asyncio
async def test_unload_failure_preserves_registered_runtime(monkeypatch) -> None:
    config_entries = SimpleNamespace(
        async_unload_platforms=AsyncMock(return_value=False)
    )
    hass = SimpleNamespace(config_entries=config_entries)
    entry = SimpleNamespace(
        data={CONF_ENTRY_DATA_FSM_CONFIG: {CONF_ID: "test_fsm"}}
    )
    unregister = AsyncMock()
    monkeypatch.setattr("custom_components.fsm.async_unregister_fsm", unregister)

    assert await async_unload_entry(hass, entry) is False
    unregister.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_unload_unregisters_runtime(monkeypatch) -> None:
    config_entries = SimpleNamespace(
        async_unload_platforms=AsyncMock(return_value=True)
    )
    hass = SimpleNamespace(config_entries=config_entries)
    entry = SimpleNamespace(
        data={CONF_ENTRY_DATA_FSM_CONFIG: {CONF_ID: "test_fsm"}}
    )
    unregister = AsyncMock()
    monkeypatch.setattr("custom_components.fsm.async_unregister_fsm", unregister)

    assert await async_unload_entry(hass, entry) is True
    unregister.assert_awaited_once_with(hass, "test_fsm")


@pytest.mark.asyncio
async def test_platform_setup_failure_rolls_back_registered_runtime(monkeypatch) -> None:
    config_entries = SimpleNamespace(
        async_forward_entry_setups=AsyncMock(side_effect=RuntimeError("boom"))
    )
    hass = SimpleNamespace(
        config_entries=config_entries,
        data={DOMAIN: {DATA_CONFIGS: {}}},
    )
    entry = SimpleNamespace(
        entry_id="entry-id",
        data={CONF_ENTRY_DATA_FSM_CONFIG: {CONF_ID: "test_fsm"}},
    )
    fsm_config = SimpleNamespace(id="test_fsm")
    unregister = AsyncMock()
    monkeypatch.setattr(
        "custom_components.fsm.parse_fsm_config_item",
        lambda config: fsm_config,
    )
    monkeypatch.setattr(
        "custom_components.fsm.register_fsm",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr("custom_components.fsm.async_unregister_fsm", unregister)

    with pytest.raises(RuntimeError, match="boom"):
        await async_setup_entry(hass, entry)

    unregister.assert_awaited_once_with(hass, "test_fsm")


@pytest.mark.asyncio
async def test_setup_entry_success_returns_bool(monkeypatch) -> None:
    """Regression: async_setup_entry must return a bool.

    Home Assistant (config_entries.py) requires a bool return; a None return
    (e.g. from a missing `return True`) marks the entry as SETUP_ERROR with
    "did not return boolean" in the logs and "Failed to set up" in the UI.
    """
    config_entries = SimpleNamespace(async_forward_entry_setups=AsyncMock())
    hass = SimpleNamespace(
        config_entries=config_entries,
        data={DOMAIN: {DATA_CONFIGS: {}}},
    )
    entry = SimpleNamespace(
        entry_id="entry-id",
        data={CONF_ENTRY_DATA_FSM_CONFIG: {CONF_ID: "test_fsm"}},
        async_on_unload=MagicMock(return_value=lambda: None),
        add_update_listener=MagicMock(return_value=object()),
    )
    fsm_config = SimpleNamespace(id="test_fsm")
    monkeypatch.setattr(
        "custom_components.fsm.parse_fsm_config_item",
        lambda config: fsm_config,
    )
    monkeypatch.setattr(
        "custom_components.fsm.register_fsm",
        lambda *args, **kwargs: object(),
    )

    result = await async_setup_entry(hass, entry)

    assert result is True


@pytest.mark.asyncio
async def test_setup_entry_duplicate_active_raises_config_entry_error(monkeypatch) -> None:
    """Duplicate setup of an already-active FSM raises ConfigEntryError."""
    hass = SimpleNamespace(
        data={DOMAIN: {DATA_CONFIGS: {"test_fsm": object()}}},
    )
    entry = SimpleNamespace(
        entry_id="entry-id",
        data={CONF_ENTRY_DATA_FSM_CONFIG: {CONF_ID: "test_fsm"}},
    )

    with pytest.raises(ConfigEntryError, match="already active"):
        await async_setup_entry(hass, entry)


class _FakeEntry:
    def __init__(self, unique_id: str, entry_id: str) -> None:
        self.unique_id = unique_id
        self.entry_id = entry_id


class _FakeConfigEntries:
    def __init__(self, entries: list[_FakeEntry]) -> None:
        self._entries = entries
        self.removed: list[str] = []

    def async_entries(self, domain: str) -> list[_FakeEntry]:
        return self._entries

    async def async_remove(self, entry_id: str) -> None:
        self.removed.append(entry_id)


class _FakeSetupHass:
    def __init__(self, entries: list[_FakeEntry]) -> None:
        self.data = {}
        self.config_entries = _FakeConfigEntries(entries)
        self.created_tasks: list = []

    def async_create_task(self, coro, eager_start: bool = False) -> None:
        self.created_tasks.append(coro)
        coro.close()  # discard the coroutine to avoid "never awaited" warnings


@pytest.mark.asyncio
async def test_async_setup_removes_orphaned_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.fsm.async_register_services", AsyncMock()
    )
    hass = _FakeSetupHass(
        [_FakeEntry("keep", "entry-keep"), _FakeEntry("orphan", "entry-orphan")]
    )

    result = await async_setup(
        hass,
        {CONF_FSM: [{CONF_ID: "keep"}]},
    )

    assert result is True
    assert hass.config_entries.removed == ["entry-orphan"]


@pytest.mark.asyncio
async def test_async_setup_keeps_matching_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.fsm.async_register_services", AsyncMock()
    )
    hass = _FakeSetupHass([_FakeEntry("keep", "entry-keep")])

    result = await async_setup(
        hass,
        {CONF_FSM: [{CONF_ID: "keep"}]},
    )

    assert result is True
    assert hass.config_entries.removed == []


@pytest.mark.asyncio
async def test_async_setup_empty_fsm_does_not_defer_import(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.fsm.async_register_services", AsyncMock()
    )
    hass = _FakeSetupHass([])

    result = await async_setup(hass, {CONF_FSM: []})

    assert result is True
    assert hass.created_tasks == []


@pytest.mark.asyncio
async def test_async_setup_defers_import_when_fsm_present(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.fsm.async_register_services", AsyncMock()
    )
    hass = _FakeSetupHass([])

    result = await async_setup(
        hass,
        {CONF_FSM: [{CONF_ID: "keep"}]},
    )

    assert result is True
    assert len(hass.created_tasks) == 1
