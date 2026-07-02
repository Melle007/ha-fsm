from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.fsm.const import EVENT_ACTION_FAILED, EVENT_TRIGGER_EVALUATION
from custom_components.fsm.models import FSMConfig, TransitionConfig, TriggerConfig
from custom_components.fsm.exceptions import FSMRuntimeError
from custom_components.fsm.runtime import FSMRuntime
from custom_components.fsm.trigger_manager import TriggerManager


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def async_fire(self, event_type: str, event_data: dict, context=None) -> None:
        self.events.append((event_type, event_data))


class _FakeHass(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(bus=_FakeBus())


@pytest.fixture
def runtime_config() -> FSMConfig:
    return FSMConfig(
        id="test_fsm",
        name="Test FSM",
        states=["idle", "active", "fallback"],
        initial_state="idle",
        restore_state=True,
        triggers=[TriggerConfig(id="go", platform="event", config={})],
        transitions=[
            TransitionConfig(from_state="idle", to_state="active", trigger_id="go", id="exact"),
            TransitionConfig(from_state="*", to_state="fallback", trigger_id="go", id="wildcard"),
        ],
        variables={},
        evaluate_on_start=False,
    )


@pytest.mark.asyncio
async def test_exact_transition_has_precedence_over_wildcard(runtime_config: FSMConfig) -> None:
    runtime = FSMRuntime(_FakeHass(), runtime_config)
    runtime.trigger_setup_complete = True
    runtime.initialized = True

    with patch("custom_components.fsm.runtime.run_actions", new=AsyncMock()):
        await runtime.async_handle_trigger("go", {})

    assert runtime.state == "active"
    assert runtime.last_transition == "idle -> active"


@pytest.mark.asyncio
async def test_async_force_state_uses_constant_marker(runtime_config: FSMConfig) -> None:
    runtime = FSMRuntime(_FakeHass(), runtime_config)

    await runtime.async_force_state("active")

    assert runtime.last_trigger_id == "__set_state__"


@pytest.mark.asyncio
async def test_trigger_evaluation_event_is_emitted(runtime_config: FSMConfig) -> None:
    hass = _FakeHass()
    runtime = FSMRuntime(hass, runtime_config)
    runtime.trigger_setup_complete = True
    runtime.initialized = True

    with patch("custom_components.fsm.runtime.run_actions", new=AsyncMock()):
        await runtime.async_handle_trigger("go", {})

    eval_events = [
        event_data
        for event_type, event_data in hass.bus.events
        if event_type == EVENT_TRIGGER_EVALUATION
    ]
    assert len(eval_events) == 1
    assert eval_events[0]["fsm_id"] == "test_fsm"
    assert eval_events[0]["matched"] is True
    assert isinstance(eval_events[0]["duration_ms"], float)


@pytest.mark.asyncio
async def test_trigger_setup_error_contains_structured_context(
    runtime_config: FSMConfig,
) -> None:
    runtime_config.triggers = [
        TriggerConfig(id="broken", platform="state", config={"entity_id": "sensor.x"})
    ]
    runtime = FSMRuntime(_FakeHass(), runtime_config)
    manager = TriggerManager(runtime.hass, runtime)

    async def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    with patch(
        "custom_components.fsm.trigger_manager.async_initialize_triggers",
        new=AsyncMock(side_effect=_raise),
    ):
        await manager.async_setup()

    assert runtime.trigger_attach_failure_count == 1
    assert len(runtime.trigger_attach_errors) == 1
    assert "platform=state" in runtime.trigger_attach_errors[0]
    assert "fsm_id=test_fsm" in runtime.trigger_attach_errors[0]


@pytest.mark.asyncio
async def test_unmatched_trigger_emits_non_match_event(runtime_config: FSMConfig) -> None:
    hass = _FakeHass()
    runtime = FSMRuntime(hass, runtime_config)
    runtime.trigger_setup_complete = True
    runtime.initialized = True

    with patch("custom_components.fsm.runtime.run_actions", new=AsyncMock()):
        await runtime.async_handle_trigger("unknown", {"source": "test"})

    assert runtime.state == "idle"
    eval_events = [
        event_data
        for event_type, event_data in hass.bus.events
        if event_type == EVENT_TRIGGER_EVALUATION
    ]
    assert len(eval_events) == 0


def test_runtime_logs_warning_for_mixed_guarded_and_unguarded_transitions() -> None:
    config = FSMConfig(
        id="ambiguous_fsm",
        name="Ambiguous FSM",
        states=["idle", "active", "fallback"],
        initial_state="idle",
        restore_state=True,
        triggers=[TriggerConfig(id="go", platform="event", config={})],
        transitions=[
            TransitionConfig(
                from_state="idle",
                to_state="active",
                trigger_id="go",
                guard="{{ true }}",
                id="guarded",
            ),
            TransitionConfig(
                from_state="idle",
                to_state="fallback",
                trigger_id="go",
                id="unguarded",
            ),
        ],
        variables={},
        evaluate_on_start=False,
    )

    with patch("custom_components.fsm.runtime._LOGGER.warning") as warn_mock:
        FSMRuntime(_FakeHass(), config)

    assert warn_mock.call_count == 1
    assert "mixed guarded/unguarded transitions" in warn_mock.call_args[0][0]


def test_runtime_logs_warning_for_multiple_unguarded_transitions() -> None:
    config = FSMConfig(
        id="double_unguarded_fsm",
        name="Double Unguarded FSM",
        states=["idle", "active", "fallback"],
        initial_state="idle",
        restore_state=True,
        triggers=[TriggerConfig(id="go", platform="event", config={})],
        transitions=[
            TransitionConfig(
                from_state="idle",
                to_state="active",
                trigger_id="go",
                id="first",
            ),
            TransitionConfig(
                from_state="idle",
                to_state="fallback",
                trigger_id="go",
                id="second",
            ),
        ],
        variables={},
        evaluate_on_start=False,
    )

    with patch("custom_components.fsm.runtime._LOGGER.warning") as warn_mock:
        FSMRuntime(_FakeHass(), config)

    assert warn_mock.call_count == 1
    assert "multiple unguarded transitions" in warn_mock.call_args[0][0]


@pytest.mark.asyncio
async def test_async_force_state_rejects_unknown_state(runtime_config: FSMConfig) -> None:
    runtime = FSMRuntime(_FakeHass(), runtime_config)

    with pytest.raises(FSMRuntimeError):
        await runtime.async_force_state("missing_state")


@pytest.mark.asyncio
async def test_trigger_setup_success_marks_runtime_ready(runtime_config: FSMConfig) -> None:
    runtime = FSMRuntime(_FakeHass(), runtime_config)
    manager = TriggerManager(runtime.hass, runtime)

    with patch.object(
        TriggerManager,
        "_attach_event_trigger",
        return_value=lambda: None,
    ):
        await manager.async_setup()

    assert runtime.trigger_setup_complete is True
    assert runtime.trigger_attach_failure_count == 0


@pytest.mark.asyncio
async def test_action_failure_keeps_old_state(runtime_config: FSMConfig) -> None:
    hass = _FakeHass()
    runtime = FSMRuntime(hass, runtime_config)
    runtime.trigger_setup_complete = True
    runtime.initialized = True

    with patch(
        "custom_components.fsm.runtime.run_actions",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await runtime.async_handle_trigger("go", {})

    assert runtime.state == "idle"
    assert runtime.transition_count == 0
    assert runtime.last_action_error == "boom"
    assert any(event_type == EVENT_ACTION_FAILED for event_type, _ in hass.bus.events)
