"""Tests for the FSM config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.fsm.config_flow import FSMConfigFlow
from custom_components.fsm.const import (
    CONF_ENTRY_DATA_FSM_CONFIG,
    CONF_ID,
    CONF_NAME,
)


class _FakeFlow(FSMConfigFlow):
    """FSMConfigFlow that skips ConfigFlow.__init__ to avoid HA dependency."""

    def __init__(self) -> None:
        # Do NOT call super().__init__()
        self._unique_id = None

    async def async_set_unique_id(self, unique_id=None):
        self._unique_id = unique_id

    def async_abort(self, *, reason, description_placeholders=None):
        return {
            "type": "abort",
            "reason": reason,
            "description_placeholders": description_placeholders,
        }

    def _abort_if_unique_id_configured(self, **kwargs):
        """No-op by default; override in tests that want it to abort."""
        pass

    def async_create_entry(self, *, title, data):
        return {
            "type": "aborted",
            "title": title,
            "data": data,
        }


@pytest.mark.asyncio
async def test_user_step_aborts_yaml_only() -> None:
    """User-initiated flow should abort with YAML-only message."""
    flow = _FakeFlow()

    result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "yaml_only"


@pytest.mark.asyncio
async def test_import_creates_entry() -> None:
    """Import step should create a config entry with proper data."""
    flow = _FakeFlow()
    import_data = {CONF_ID: "test_light", CONF_NAME: "Test Light"}

    result = await flow.async_step_import(import_data)

    assert flow._unique_id == "test_light"
    assert result["title"] == "Test Light"
    assert result["data"][CONF_ENTRY_DATA_FSM_CONFIG] == import_data


@pytest.mark.asyncio
async def test_import_sets_unique_id() -> None:
    """Import step should set unique_id from the import data."""
    flow = _FakeFlow()
    import_data = {CONF_ID: "my_fsm_123", CONF_NAME: "My FSM"}

    await flow.async_step_import(import_data)

    assert flow._unique_id == "my_fsm_123"


@pytest.mark.asyncio
async def test_import_aborts_on_duplicate_unique_id() -> None:
    """Import step should abort when unique_id is already configured."""
    flow = _FakeFlow()
    import_data = {CONF_ID: "duplicate_fsm", CONF_NAME: "Duplicate"}

    def mock_abort_if_unique(**kwargs):
        return {"type": "abort", "reason": "already_configured"}

    with patch.object(
        flow,
        "_abort_if_unique_id_configured",
        side_effect=mock_abort_if_unique,
    ):
        result = await flow.async_step_import(import_data)

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert flow._unique_id == "duplicate_fsm"