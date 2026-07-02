from __future__ import annotations


class FSMError(Exception):
    """Base exception for FSM integration internals."""


class FSMConfigError(FSMError):
    """Raised when validated FSM configuration cannot be compiled or registered."""


class FSMRuntimeError(FSMError):
    """Raised for runtime operational failures exposed internally."""


class FSMActionError(FSMRuntimeError):
    """Raised when transition actions are invalid or fail to execute."""
