from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.fsm.models import FSMConfig, TransitionConfig, TriggerConfig
from custom_components.fsm.runtime import FSMRuntime


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def async_fire(self, event_type: str, event_data: dict, context=None) -> None:
        self.events.append((event_type, event_data))


class _FakeHass(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(bus=_FakeBus())


@pytest.fixture
def load_runtime() -> FSMRuntime:
    config = FSMConfig(
        id="load_fsm",
        name="Load FSM",
        states=["idle", "active"],
        initial_state="idle",
        restore_state=True,
        triggers=[TriggerConfig(id="toggle", platform="event", config={})],
        transitions=[
            TransitionConfig(
                from_state="idle",
                to_state="active",
                trigger_id="toggle",
                id="idle_to_active",
            ),
            TransitionConfig(
                from_state="active",
                to_state="idle",
                trigger_id="toggle",
                id="active_to_idle",
            ),
        ],
        variables={},
        evaluate_on_start=False,
    )
    runtime = FSMRuntime(_FakeHass(), config)
    runtime.trigger_setup_complete = True
    runtime.initialized = True
    return runtime


@pytest.mark.asyncio
async def test_runtime_sequential_load_ci_safe(load_runtime: FSMRuntime) -> None:
    iterations = 2000

    with patch("custom_components.fsm.runtime.run_actions", new=AsyncMock()):
        start = time.perf_counter()
        for _ in range(iterations):
            await load_runtime.async_handle_trigger("toggle", {"source": "load"})
        duration_s = time.perf_counter() - start

    assert load_runtime.transition_count == iterations
    assert load_runtime.state == "idle"

    avg_ms = (duration_s * 1000) / iterations
    # CI-safe threshold: catches major regressions without being flaky on shared runners.
    assert avg_ms < 5.0


@pytest.mark.asyncio
@pytest.mark.stress
async def test_runtime_concurrent_burst_stress(load_runtime: FSMRuntime) -> None:
    burst_size = 500

    with patch("custom_components.fsm.runtime.run_actions", new=AsyncMock()):
        start = time.perf_counter()
        await asyncio.gather(
            *[
                load_runtime.async_handle_trigger("toggle", {"idx": i})
                for i in range(burst_size)
            ]
        )
        duration_s = time.perf_counter() - start

    assert load_runtime.transition_count == burst_size
    assert load_runtime.state == ("idle" if burst_size % 2 == 0 else "active")

    avg_ms = (duration_s * 1000) / burst_size
    # Stress threshold is intentionally lenient; this test is mainly for local profiling.
    assert avg_ms < 10.0
