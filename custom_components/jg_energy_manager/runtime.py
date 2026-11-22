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
    was_connected: bool = False
    energy_baseline_kwh: float | None = None
    integrated_energy_kwh: float = 0.0
    session_energy_kwh: float = 0.0
    vehicle_satisfied: bool = False
    low_demand_since: str | None = None
    last_sample_at: str | None = None
    last_energy_total_kwh: float | None = None

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
