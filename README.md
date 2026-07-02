# Finite State Machine (FSM)

A YAML-first Home Assistant custom integration that exposes configurable finite state machines as `select` entities.

Use it when a Home Assistant automation is easier to model as explicit states and transitions than as many independent helpers, scripts, and conditions.

Each configured FSM is exposed as a Home Assistant `select` entity. Triggers determine **when** transitions are evaluated, while transitions determine **if** and **how** the FSM changes state.

## Features

- Define one or more finite state machines in YAML.
- Expose each FSM as a Home Assistant `select` entity.
- Manually select a state from the entity to force the FSM into that state.
- Restore the last state after restart, or start from the configured initial state.
- Drive transitions from Home Assistant triggers.
- Use exact transitions and wildcard/global transitions.
- Add Jinja guard templates to transitions.
- Run Home Assistant actions before a state change is committed.
- Trigger transitions or force a state through services.
- Emit events for debugging and automation.

## Installation

### Manual

1. Copy this folder to:

   ```text
   <config>/custom_components/fsm
   ```

2. Restart Home Assistant.
3. Add an `fsm:` section to `configuration.yaml`.
4. Restart Home Assistant again after changing YAML configuration.

### HACS custom repository

Until this integration is published as a default HACS repository:

1. Open HACS.
2. Go to **Integrations**.
3. Open the menu and choose **Custom repositories**.
4. Add the GitHub repository URL.
5. Select category **Integration**.
6. Install and restart Home Assistant.

## Minimal example

```yaml
fsm:
  - id: alarm_mode_fsm
    name: Alarm Mode FSM
    states:
      - disarmed
      - armed_home
      - armed_away
    initial_state: disarmed
    triggers:
      - id: arm_home
        platform: event
        event_type: alarm_arm_home
      - id: disarm
        platform: event
        event_type: alarm_disarm
    transitions:
      - from: disarmed
        to: armed_home
        trigger_id: arm_home
      - from: "*"
        to: disarmed
        trigger_id: disarm
```

This creates a `select` entity named `Alarm Mode FSM` with the configured states as options.

When the `arm_home` event is received, the FSM transitions from `disarmed` to `armed_home`. The `disarm` trigger uses a wildcard transition (`from: "*"`) so it can return the FSM to `disarmed` from any state.

## State-centric syntax

For larger state machines, transitions can be defined directly under each state instead of using a top-level `transitions:` list.

In this syntax, each state's `on` section maps a `trigger_id` to one or more transitions originating from that state.

```yaml
fsm:
  - id: ventilation_fsm
    name: Ventilation FSM
    states:
      idle:
        on:
          co2_high:
            to: boost
            actions:
              - action: notify.mobile_app_phone
                data:
                  message: "CO₂ level is high. Ventilation switched to boost."

      boost:
        on:
          co2_ok:
            to: idle
            actions:
              - action: notify.mobile_app_phone
                data:
                  message: "CO₂ level is normal. Ventilation returned to idle."

      fault: {}

    initial_state: idle

    triggers:
      - id: co2_high
        platform: numeric_state
        entity_id: sensor.living_room_co2
        above: 1200

      - id: co2_ok
        platform: numeric_state
        entity_id: sensor.living_room_co2
        below: 900
```

Multiple candidate transitions for the same trigger are evaluated in the order they are defined. The first transition whose guard (if any) evaluates to `true` is taken.

A trigger only evaluates transitions that reference its `trigger_id`.

## Explicit transition syntax

```yaml
transitions:
  - from: idle
    to: active
    trigger_id: motion
    guard: "{{ is_state('binary_sensor.house_occupied', 'on') }}"
    actions:
      - action: light.turn_on
        target:
          entity_id: light.hallway
```

`from` and `trigger_id` also accept lists:

```yaml
transitions:
  - from: [idle, waiting]
    to: active
    trigger_id: [motion, button_pressed]
```

## Global wildcard transitions

Use `global:` for transitions available from every state:

```yaml
global:
  on:
    reset:
      to: idle
```

This is equivalent to a transition with `from: "*"`.

Exact state transitions are evaluated before wildcard transitions.

## Startup evaluation

Set `evaluate_on_start: true` and use the internal trigger `__startup__`:

```yaml
fsm:
  - id: startup_example
    name: Startup Example
    states:
      idle: {}
      active: {}
    initial_state: idle
    evaluate_on_start: true
    triggers:
      - id: dummy
        platform: event
        event_type: dummy_event
    global:
      on:
        - trigger_id: __startup__
          to: active
          guard: "{{ is_state('input_boolean.enable_startup_mode', 'on') }}"
```

## Restore behavior

`restore_state` defaults to `true`.

```yaml
restore_state: true
```

When enabled, Home Assistant restore state is used if the previous state is still valid. Otherwise the FSM starts from `initial_state`.

## Variables and templates

Optional `variables:` define reusable values that are available to guard templates, actions, and other variables.

Example:

```yaml
fsm:
  - id: living_room_lights
    name: Living Room Lights
    states: ["off", "on"]
    initial_state: "off"
    restore_state: true

    variables:
      room: "Living Room"
      icon: "💡"

      # Variables can reference other variables and template context
      notification_title: "{{ icon }} {{ room }}"
      notification_message: >
        Lights in {{ room }} changed from {{ from_state }}
        to {{ to_state }}.

    triggers:
      - id: light_on
        platform: state
        entity_id: light.living_room
        to: "on"

      - id: light_off
        platform: state
        entity_id: light.living_room
        to: "off"

    transitions:
      - from: "off"
        to: "on"
        trigger_id: light_on
        actions:
          - action: notify.mobile_app_phone
            data:
              title: "{{ notification_title }}"
              message: "{{ notification_message }}"

      - from: "on"
        to: "off"
        trigger_id: light_off
        actions:
          - action: notify.mobile_app_phone
            data:
              title: "{{ notification_title }}"
              message: "{{ notification_message }}"
``` 

Reserved variable names are not allowed: `fsm`, `variables`, `trigger`, `trigger_id`, `transition`, `from_state`, `to_state`.

Template context includes:

- `fsm.id`
- `fsm.name`
- `fsm.state`
- `fsm.previous_state`
- `variables`
- `trigger`
- `trigger_id`
- `transition.from`
- `transition.to`
- `transition.trigger_id`
- `from_state`
- `to_state`

You can define `variables:` values that may be static values or templates.

## Actions

Actions use modern Home Assistant action syntax:

```yaml
actions:
  - action: notify.mobile_app_phone
    data:
      message: "FSM {{ fsm.id }} changed from {{ from_state }} to {{ to_state }}"
```

Old `service:` and `service_template:` keys are intentionally rejected.

Actions run before the state change is committed. If every action succeeds, the FSM enters the new state. If an action fails, the state remains unchanged and an `fsm_action_failed` event is emitted.

## Services

### `fsm.trigger`

Trigger a configured FSM transition manually.

Fields:

- `fsm_id` or `entity_id`
- `trigger_id`

Example:

```yaml
action: fsm.trigger
data:
  fsm_id: alarm_mode_fsm
  trigger_id: arm_home
```

### `fsm.set_state`

Force the current state immediately, bypassing transition matching, guards, and actions.

Fields:

- `fsm_id` or `entity_id`
- `state`

Example:

```yaml
action: fsm.set_state
data:
  fsm_id: alarm_mode_fsm
  state: disarmed
```

## Events

The integration emits these events:

- `fsm_trigger_received`
- `fsm_trigger_evaluation`
- `fsm_transition`
- `fsm_action_failed`

These are useful for debugging or building automations around FSM behavior.

## Entity attributes

Each FSM entity exposes diagnostics such as:

- `fsm_id`
- `states`
- `initial_state`
- `current_state`
- `previous_state`
- `last_trigger_id`
- `last_transition`
- `last_transition_at`
- `transition_count`
- `transitions_summary`
- `available_trigger_ids`
- `candidate_transitions`
- `ready`
- `initialized`
- `trigger_setup_complete`
- `trigger_setup_ok`
- `restored`
- `last_error`
- `last_action_error`

## Limitations

- Configuration is YAML-first.
- The UI config flow only shows a friendly unsupported message.
- FSM definitions require a Home Assistant restart after YAML changes.
- The FSM entity is a `select` entity; selecting an option force-sets the state.

## Development

From a Home Assistant checkout with this integration under `custom_components/fsm`:

```bash
source <path-to-venv>/bin/activate
cd <path-to-home-assistant>
python -m pytest custom_components/fsm/tests
```

To skip local stress tests:

```bash
python -m pytest custom_components/fsm/tests -m "not stress"
```
