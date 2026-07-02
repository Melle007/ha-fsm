DOMAIN = "fsm"
PLATFORM_SELECT = "select"

CONF_FSM = "fsm"
CONF_ID = "id"
CONF_NAME = "name"
CONF_STATES = "states"
CONF_INITIAL_STATE = "initial_state"
CONF_RESTORE_STATE = "restore_state"
CONF_EVALUATE_ON_START = "evaluate_on_start"
CONF_TRIGGERS = "triggers"
CONF_TRANSITIONS = "transitions"
CONF_GLOBAL = "global"
CONF_ON = "on"
CONF_FROM = "from"
CONF_TO = "to"
CONF_TRIGGER_ID = "trigger_id"
CONF_PLATFORM = "platform"
CONF_GUARD = "guard"
CONF_ACTIONS = "actions"
CONF_VARIABLES = "variables"

DATA_CONFIGS = "configs"
DATA_RUNTIMES = "runtimes"
DATA_ENTITIES = "entities"
DATA_PENDING_ENTITIES = "pending_entities"

SERVICE_TRIGGER = "trigger"
SERVICE_SET_STATE = "set_state"
SERVICE_FIELD_ENTITY_ID = "entity_id"
SERVICE_FIELD_FSM_ID = "fsm_id"
SERVICE_FIELD_TRIGGER_ID = "trigger_id"
SERVICE_FIELD_STATE = "state"

FORCED_STATE_TRIGGER_ID = "__set_state__"
INTERNAL_STARTUP_TRIGGER_ID = "__startup__"

EVENT_TRIGGER_RECEIVED = "fsm_trigger_received"
EVENT_TRIGGER_EVALUATION = "fsm_trigger_evaluation"
EVENT_TRANSITION = "fsm_transition"
EVENT_ACTION_FAILED = "fsm_action_failed"

ATTR_FSM_ID = "fsm_id"
ATTR_STATES = "states"
ATTR_INITIAL_STATE = "initial_state"
ATTR_CURRENT_STATE = "current_state"
ATTR_PREVIOUS_STATE = "previous_state"
ATTR_LAST_TRIGGER_ID = "last_trigger_id"
ATTR_LAST_TRANSITION = "last_transition"
ATTR_LAST_TRANSITION_AT = "last_transition_at"
ATTR_TRANSITION_COUNT = "transition_count"
ATTR_TRANSITIONS_SUMMARY = "transitions_summary"
ATTR_AVAILABLE_TRIGGER_IDS = "available_trigger_ids"
ATTR_CANDIDATE_TRANSITIONS = "candidate_transitions"
ATTR_READY = "ready"
ATTR_INITIALIZED = "initialized"
ATTR_TRIGGER_SETUP_COMPLETE = "trigger_setup_complete"
ATTR_TRIGGER_SETUP_OK = "trigger_setup_ok"
ATTR_MATCH_PRECEDENCE = "match_precedence"
ATTR_RESTORED = "restored"
ATTR_LAST_ERROR = "last_error"
ATTR_LAST_ACTION_ERROR = "last_action_error"
ATTR_TRIGGER_ATTACH_SUCCESS_COUNT = "trigger_attach_success_count"
ATTR_TRIGGER_ATTACH_FAILURE_COUNT = "trigger_attach_failure_count"
ATTR_TRIGGER_ATTACH_ERRORS = "trigger_attach_errors"

RESERVED_VARIABLE_NAMES = {
    "fsm",
    "variables",
    "trigger",
    "trigger_id",
    "transition",
    "from_state",
    "to_state",
}
