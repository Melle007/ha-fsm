from __future__ import annotations

from types import SimpleNamespace

from custom_components.fsm.entity import FSMEntity
from custom_components.fsm.models import FSMConfig, TransitionConfig, TriggerConfig
from custom_components.fsm.runtime import FSMRuntime


class _FakeBus:
    def async_fire(self, event_type: str, event_data: dict, context=None) -> None:
        pass


class _FakeHass(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(bus=_FakeBus())


def _runtime(*, debug: bool) -> FSMRuntime:
    config = FSMConfig(
        id="test_fsm",
        name="Test FSM",
        states=["idle", "active"],
        initial_state="idle",
        restore_state=True,
        debug=debug,
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
    return FSMRuntime(_FakeHass(), config)


def test_extra_state_attributes_are_compact_by_default() -> None:
    entity = FSMEntity(_runtime(debug=False))

    attributes = entity.extra_state_attributes

    assert attributes["fsm_id"] == "test_fsm"
    assert attributes["ready"] is False
    assert attributes["last_error"] is None
    assert attributes["last_action_error"] is None
    assert "current_state" not in attributes
    assert "states" not in attributes
    assert "transitions_summary" not in attributes
    assert "trigger_attach_errors" not in attributes


def test_extra_state_attributes_include_diagnostics_when_debug_enabled() -> None:
    entity = FSMEntity(_runtime(debug=True))

    attributes = entity.extra_state_attributes

    assert attributes["fsm_id"] == "test_fsm"
    assert attributes["ready"] is False
    assert attributes["current_state"] == "idle"
    assert attributes["previous_state"] is None
    assert attributes["last_error"] is None
    assert attributes["last_action_error"] is None
    assert attributes["states"] == ["idle", "active"]
    assert attributes["initial_state"] == "idle"
    assert attributes["transitions_summary"] == ["idle -> active [go]"]
    assert attributes["trigger_attach_errors"] == []
