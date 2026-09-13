"""Tests for the select platform setup entry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.fsm.const import (
    CONF_ENTRY_DATA_FSM_CONFIG,
    CONF_ID,
    DATA_ENTITIES,
    DOMAIN,
)
from custom_components.fsm.select import async_setup_entry


class _FakeEntry:
    def __init__(self, fsm_id: str):
        self.data = {
            CONF_ENTRY_DATA_FSM_CONFIG: {CONF_ID: fsm_id, "name": "Test FSM"}
        }


@pytest.mark.asyncio
async def test_setup_entry_adds_registered_entity() -> None:
    entity = object()
    hass = SimpleNamespace(
        data={DOMAIN: {DATA_ENTITIES: {"test_fsm": entity}}}
    )
    added: list = []
    async_add_entities = lambda entities: added.extend(entities)

    await async_setup_entry(hass, _FakeEntry("test_fsm"), async_add_entities)

    assert added == [entity]


@pytest.mark.asyncio
async def test_setup_entry_without_registered_entity_does_not_add() -> None:
    hass = SimpleNamespace(data={DOMAIN: {DATA_ENTITIES: {}}})
    added: list = []
    async_add_entities = lambda entities: added.extend(entities)

    await async_setup_entry(hass, _FakeEntry("missing"), async_add_entities)

    assert added == []
