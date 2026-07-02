from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TriggerConfig:
    id: str
    platform: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TransitionConfig:
    from_state: str
    to_state: str
    trigger_id: str
    guard: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    id: str | None = None


@dataclass(slots=True)
class FSMConfig:
    id: str
    name: str
    states: list[str]
    initial_state: str
    restore_state: bool = True
    triggers: list[TriggerConfig] = field(default_factory=list)
    transitions: list[TransitionConfig] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    evaluate_on_start: bool = False
