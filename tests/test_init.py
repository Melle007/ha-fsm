"""Tests for config-entry lifecycle behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.fsm import (
    _async_update_listener,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.fsm.const import (
    CONF_ENTRY_DATA_FSM_CONFIG,
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
