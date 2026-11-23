"""Unconditional, testable snapshots of configured Home Assistant inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

InputKind = Literal["numeric", "text"]
INVALID_STATES = {"unknown", "unavailable", "none", ""}


@dataclass(frozen=True, slots=True)
class InputRole:
    """A configured entity role and its validation contract."""

    name: str
    config_key: str
    kind: InputKind
    required: bool = True


@dataclass(frozen=True, slots=True)
class InputReading:
    """One entity reading without exposing its entity ID."""

    role: str
    value: float | str | None
    raw_state: str | None
    health: str
    required: bool


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    """Complete point-in-time snapshot of every configured live input."""

    readings: dict[str, InputReading]

    def numeric(self, role: str) -> float | None:
        value = self.readings[role].value
        return value if isinstance(value, float) else None

    def text(self, role: str) -> str | None:
        value = self.readings[role].value
        return value if isinstance(value, str) else None

    @property
    def missing_roles(self) -> list[str]:
        return sorted(
            reading.role
            for reading in self.readings.values()
            if reading.required and reading.health in {"not_configured", "missing"}
        )

    @property
    def invalid_roles(self) -> list[str]:
        return sorted(
            reading.role
            for reading in self.readings.values()
            if reading.required and reading.health == "invalid"
        )

    @property
    def degraded_optional_roles(self) -> list[str]:
        return sorted(
            reading.role
            for reading in self.readings.values()
            if not reading.required and reading.health != "valid"
        )

    @property
    def valid(self) -> bool:
        return not self.missing_roles and not self.invalid_roles

    def redacted_health(self) -> dict[str, dict[str, Any]]:
        """Return role health and raw state, never configured entity IDs."""
        return {
            name: {
                "health": reading.health,
                "state": reading.raw_state,
                "required": reading.required,
            }
            for name, reading in sorted(self.readings.items())
        }


def _read_role(
    settings: dict[str, Any],
    role: InputRole,
    get_state: Callable[[str], Any | None],
) -> InputReading:
    entity_id = settings.get(role.config_key)
    if not entity_id:
        return InputReading(role.name, None, None, "not_configured", role.required)

    state = get_state(entity_id)
    if state is None:
        return InputReading(role.name, None, None, "missing", role.required)

    raw = getattr(state, "state", None)
    raw_text = None if raw is None else str(raw)
    if raw_text is None or raw_text.casefold() in INVALID_STATES:
        return InputReading(role.name, None, raw_text, "invalid", role.required)

    if role.kind == "text":
        return InputReading(role.name, raw_text, raw_text, "valid", role.required)

    try:
        # Explicit conversion preserves valid numeric zero. Never use truthiness.
        value = float(raw_text)
    except (TypeError, ValueError):
        return InputReading(role.name, None, raw_text, "invalid", role.required)
    return InputReading(role.name, value, raw_text, "valid", role.required)


def snapshot_inputs(
    settings: dict[str, Any],
    roles: tuple[InputRole, ...],
    get_state: Callable[[str], Any | None],
) -> InputSnapshot:
    """Read every role directly from the HA state machine on every invocation."""
    return InputSnapshot(
        {
            role.name: _read_role(settings, role, get_state)
            for role in roles
        }
    )
