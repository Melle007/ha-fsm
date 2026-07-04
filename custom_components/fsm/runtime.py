from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.template import Template

from .action_validation import normalize_actions
from .actions import compile_actions, run_actions
from .const import (
    EVENT_ACTION_FAILED,
    EVENT_TRIGGER_EVALUATION,
    EVENT_TRANSITION,
    EVENT_TRIGGER_RECEIVED,
    FORCED_STATE_TRIGGER_ID,
    INTERNAL_STARTUP_TRIGGER_ID,
)
from .exceptions import FSMConfigError, FSMRuntimeError
from .models import FSMConfig, TransitionConfig
from .templating import build_fsm_context

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _CompiledTransition:
    transition: TransitionConfig
    compiled_guard_template: Template | None
    compiled_actions: list[dict[str, Any]]


class FSMRuntime:
    """Runtime state and transition engine for a single configured FSM."""

    def __init__(self, hass: HomeAssistant, config: FSMConfig) -> None:
        self.hass = hass
        self.config = config
        self.entity: Any | None = None
        self.trigger_manager: Any | None = None

        self.state: str = config.initial_state
        self.previous_state: str | None = None
        self.last_trigger_id: str | None = None
        self.last_transition: str | None = None
        self.last_transition_at: datetime | None = None
        self.transition_count: int = 0

        self.initialized: bool = False
        self.trigger_setup_complete: bool = False
        self.state_restored: bool = False
        self.last_error: str | None = None
        self.last_action_error: str | None = None
        self.trigger_attach_success_count: int = 0
        self.trigger_attach_failure_count: int = 0
        self.trigger_attach_errors: list[str] = []

        self._lock = asyncio.Lock()
        self._transition_index: dict[tuple[str, str], list[int]] = defaultdict(list)
        self._wildcard_transition_index: dict[str, list[int]] = defaultdict(list)
        self._compiled_transitions: list[_CompiledTransition] = []

        duplicate_keys: dict[tuple[str, str], int] = defaultdict(int)

        for idx, transition in enumerate(config.transitions):
            if transition.from_state == "*":
                self._wildcard_transition_index[transition.trigger_id].append(idx)
            else:
                self._transition_index[
                    (transition.from_state, transition.trigger_id)
                ].append(idx)

            duplicate_keys[(transition.from_state, transition.trigger_id)] += 1

            guard_template = None
            if transition.guard:
                try:
                    guard_template = Template(transition.guard, hass)
                except Exception as err:
                    raise FSMConfigError(
                        f"Invalid guard template in transition {idx} "
                        f"('{transition.from_state}' -> '{transition.to_state}'): {err}"
                    ) from err

            try:
                compiled_actions = compile_actions(
                    hass,
                    normalize_actions(transition.actions),
                )
            except Exception as err:
                raise FSMConfigError(
                    f"Invalid actions in transition {idx} "
                    f"('{transition.from_state}' -> '{transition.to_state}'): {err}"
                ) from err

            self._compiled_transitions.append(
                _CompiledTransition(
                    transition=transition,
                    compiled_guard_template=guard_template,
                    compiled_actions=compiled_actions,
                )
            )

        for (from_state, trigger_id), count in duplicate_keys.items():
            if count > 1:
                _LOGGER.debug(
                    "FSM '%s' has %s transitions for from='%s' trigger='%s'; first passing guard wins",
                    self.config.id,
                    count,
                    from_state,
                    trigger_id,
                )

        self._log_transition_ambiguity_warnings()

    def _log_transition_ambiguity_warnings(self) -> None:
        """Log potentially ambiguous transition groups without changing behavior."""
        grouped: dict[tuple[str, str], list[TransitionConfig]] = defaultdict(list)
        for transition in self.config.transitions:
            grouped[(transition.from_state, transition.trigger_id)].append(transition)

        for (from_state, trigger_id), transitions in grouped.items():
            if len(transitions) <= 1:
                continue

            has_guarded = any(bool(t.guard) for t in transitions)
            has_unguarded = any(not t.guard for t in transitions)

            if has_guarded and has_unguarded:
                _LOGGER.warning(
                    "FSM '%s' has mixed guarded/unguarded transitions for from='%s' trigger='%s'. "
                    "Evaluation is order-dependent (first passing guard wins).",
                    self.config.id,
                    from_state,
                    trigger_id,
                )
            elif has_unguarded:
                _LOGGER.warning(
                    "FSM '%s' has multiple unguarded transitions for from='%s' trigger='%s'. "
                    "Only the first transition can ever match.",
                    self.config.id,
                    from_state,
                    trigger_id,
                )

    @property
    def ready(self) -> bool:
        return self.initialized and self.trigger_setup_complete

    @property
    def trigger_setup_ok(self) -> bool:
        return self.trigger_setup_complete and self.trigger_attach_failure_count == 0

    @property
    def match_precedence(self) -> str:
        return "exact_first_then_wildcard"

    @property
    def transitions_summary(self) -> list[str]:
        return [
            f"{t.from_state} -> {t.to_state} [{t.trigger_id}]"
            for t in self.config.transitions
        ]

    @property
    def available_trigger_ids(self) -> list[str]:
        trigger_ids = {
            transition.trigger_id
            for transition in self.config.transitions
            if transition.from_state in (self.state, "*")
        }
        return sorted(trigger_ids)

    @property
    def candidate_transitions(self) -> list[str]:
        return [
            f"{transition.from_state} -> {transition.to_state} [{transition.trigger_id}]"
            for transition in self.config.transitions
            if transition.from_state in (self.state, "*")
        ]

    def notify_trigger_setup_result(
        self,
        success_count: int,
        failure_count: int,
        errors: list[str],
        *,
        complete: bool = True,
    ) -> None:
        self.trigger_attach_success_count = success_count
        self.trigger_attach_failure_count = failure_count
        self.trigger_attach_errors = list(errors)
        self.trigger_setup_complete = complete
        if self.entity:
            self.entity.async_write_ha_state()

    async def async_initialize(self, state_restored_state: str | None) -> None:
        async with self._lock:
            if state_restored_state in self.config.states:
                self.state = state_restored_state
                self.state_restored = True
            else:
                self.state = self.config.initial_state
                self.state_restored = False

            self.initialized = True

            if self.entity:
                self.entity.async_write_ha_state()

    async def async_force_state(self, state: str) -> None:
        async with self._lock:
            if state not in self.config.states:
                raise FSMRuntimeError(
                    f"Invalid state '{state}' for FSM '{self.config.id}'"
                )

            self.previous_state = self.state
            self.state = state
            self.last_trigger_id = FORCED_STATE_TRIGGER_ID
            self.last_transition = f"{self.previous_state} -> {self.state}"
            self.last_transition_at = datetime.now(timezone.utc)
            self.transition_count += 1
            self.last_error = None
            self.last_action_error = None

            if self.entity:
                self.entity.async_write_ha_state()

    async def async_handle_trigger(
        self,
        trigger_id: str,
        trigger_payload: dict[str, Any] | None = None,
        context: Context | None = None,
    ) -> None:
        from .guard import evaluate_guard

        async with self._lock:
            if not self.ready:
                _LOGGER.debug(
                    "Ignoring trigger '%s' for FSM '%s' because runtime is not ready yet "
                    "(initialized=%s, trigger_setup_complete=%s)",
                    trigger_id,
                    self.config.id,
                    self.initialized,
                    self.trigger_setup_complete,
                )
                return

            current_state = self.state
            exact_candidate_indices = self._transition_index.get(
                (current_state, trigger_id),
                [],
            )
            wildcard_candidate_indices = self._wildcard_transition_index.get(
                trigger_id,
                [],
            )
            candidate_indices = [
                *exact_candidate_indices,
                *wildcard_candidate_indices,
            ]

        self.hass.bus.async_fire(
            EVENT_TRIGGER_RECEIVED,
            {
                "fsm_id": self.config.id,
                "state": current_state,
                "trigger_id": trigger_id,
                "candidate_count": len(candidate_indices),
                "exact_candidate_count": len(exact_candidate_indices),
                "wildcard_candidate_count": len(wildcard_candidate_indices),
                "match_precedence": self.match_precedence,
            },
            context=context,
        )

        eval_start = time.perf_counter()

        if not candidate_indices:
            return

        contexts_by_idx: dict[int, dict[str, Any]] = {}
        chosen_idx: int | None = None
        for idx in candidate_indices:
            transition = self.config.transitions[idx]
            rendered_context = build_fsm_context(
                self.hass,
                self,
                trigger_payload,
                transition,
                trigger_id=trigger_id,
                state=current_state,
            )
            contexts_by_idx[idx] = rendered_context
            guard_ok = await evaluate_guard(
                self.hass,
                self,
                transition,
                trigger_payload,
                compiled_template=self._compiled_transitions[
                    idx
                ].compiled_guard_template,
                rendered_context=rendered_context,
            )
            if guard_ok:
                chosen_idx = idx
                break

        if chosen_idx is None:
            self.hass.bus.async_fire(
                EVENT_TRIGGER_EVALUATION,
                {
                    "fsm_id": self.config.id,
                    "trigger_id": trigger_id,
                    "from_state": current_state,
                    "candidate_count": len(candidate_indices),
                    "matched": False,
                    "duration_ms": round((time.perf_counter() - eval_start) * 1000, 3),
                },
                context=context,
            )
            return

        chosen = self.config.transitions[chosen_idx]
        chosen_context = contexts_by_idx[chosen_idx]

        try:
            await run_actions(
                self.hass,
                self,
                self._compiled_transitions[chosen_idx].compiled_actions,
                trigger_payload,
                context,
                already_normalized=True,
                rendered_context=chosen_context,
            )
        except Exception as err:
            await self._async_record_action_failure(
                trigger_id=trigger_id,
                transition_id=chosen.id,
                error=str(err),
            )
            self.hass.bus.async_fire(
                EVENT_ACTION_FAILED,
                {
                    "fsm_id": self.config.id,
                    "state": self.state,
                    "trigger_id": trigger_id,
                    "transition_id": chosen.id,
                    "error": str(err),
                },
                context=context,
            )
            if self.entity:
                self.entity.async_write_ha_state()
            return

        try:
            chosen = await self._async_commit_transition(
                chosen_idx,
                trigger_id,
                expected_from_state=current_state,
            )
        except FSMRuntimeError as err:
            await self._async_record_action_failure(
                trigger_id=trigger_id,
                transition_id=chosen.id,
                error=str(err),
            )
            if self.entity:
                self.entity.async_write_ha_state()
            _LOGGER.warning("Skipping stale FSM transition commit: %s", err)
            return

        self.hass.bus.async_fire(
            EVENT_TRIGGER_EVALUATION,
            {
                "fsm_id": self.config.id,
                "trigger_id": trigger_id,
                "from_state": current_state,
                "candidate_count": len(candidate_indices),
                "matched": True,
                "chosen_transition": chosen.id
                or f"{chosen.from_state}->{chosen.to_state}:{chosen.trigger_id}",
                "duration_ms": round((time.perf_counter() - eval_start) * 1000, 3),
            },
            context=context,
        )

        self.hass.bus.async_fire(
            EVENT_TRANSITION,
            {
                "fsm_id": self.config.id,
                "from_state": current_state,
                "configured_from_state": chosen.from_state,
                "to_state": chosen.to_state,
                "trigger_id": trigger_id,
                "transition_id": chosen.id,
            },
            context=context,
        )

        if self.entity:
            self.entity.async_write_ha_state()

    async def _async_commit_transition(
        self,
        chosen_idx: int,
        trigger_id: str,
        *,
        expected_from_state: str,
    ) -> TransitionConfig:
        async with self._lock:
            chosen = self.config.transitions[chosen_idx]
            if self.state != expected_from_state:
                raise FSMRuntimeError(
                    f"FSM '{self.config.id}' state changed during transition selection: "
                    f"expected '{expected_from_state}', got '{self.state}'"
                )

            self.previous_state = self.state
            self.state = chosen.to_state
            self.last_trigger_id = trigger_id
            self.last_transition = f"{self.previous_state} -> {chosen.to_state}"
            self.last_transition_at = datetime.now(timezone.utc)
            self.transition_count += 1
            self.last_error = None
            self.last_action_error = None
            return chosen

    async def _async_record_action_failure(
        self,
        *,
        trigger_id: str,
        transition_id: str | None,
        error: str,
    ) -> None:
        async with self._lock:
            self.last_error = error
            self.last_action_error = error
            self.last_trigger_id = trigger_id

    async def async_evaluate_startup(self) -> None:
        await self.async_handle_trigger(
            INTERNAL_STARTUP_TRIGGER_ID,
            {"startup": True},
            None,
        )
