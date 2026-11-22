"""Persistent runtime/session state for JG Energy Manager."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class RuntimeState:
    controller_enabled: bool = True
    observe_only: bool = True
    override: str = "automatic"

    # Active session
    was_connected: bool = False
    was_charging: bool = False
    session_had_charging: bool = False
    energy_baseline_kwh: float | None = None
    integrated_energy_kwh: float = 0.0
    counter_delta_kwh: float | None = None
    session_energy_kwh: float = 0.0
    session_energy_source: str = "inactive"
    energy_meter_available: bool = False
    vehicle_satisfied: bool = False
    session_started_at: str | None = None
    session_satisfied_at: str | None = None
    satisfied_energy_kwh: float | None = None
    low_demand_since: str | None = None
    last_sample_at: str | None = None
    last_energy_total_kwh: float | None = None

    # Last completed session survives disconnection and restart.
    last_session_energy_kwh: float | None = None
    last_session_unused_allowance_kwh: float | None = None
    last_session_started_at: str | None = None
    last_session_ended_at: str | None = None
    last_session_satisfied_at: str | None = None
    last_session_end_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, observe_only: bool) -> "RuntimeState":
        state = cls(observe_only=observe_only)
        if not data:
            return state
        for field_name in state.__dataclass_fields__:
            if field_name in data:
                setattr(state, field_name, data[field_name])
        state.override = {
            "force_max": "force_charge",
            "force_off": "off",
        }.get(state.override, state.override)
        if state.override not in {"automatic", "force_charge", "solar_only", "off"}:
            state.override = "automatic"
        # v1 runtime stores did not identify the energy source. Preserve the
        # session, then let the first valid meter sample rebase without a jump.
        if state.was_connected and state.session_energy_source == "inactive":
            state.session_energy_source = "legacy_recovery"
            state.energy_meter_available = False
            state.integrated_energy_kwh = state.session_energy_kwh
        return state

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
