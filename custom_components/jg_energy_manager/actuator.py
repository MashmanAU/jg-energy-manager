"""Pure actuator command acknowledgement, retry and health state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class ActuatorState:
    """Track command issuance separately from observed acknowledgement."""

    healthy: bool = True
    status: str = "not_tested"
    last_requested_current_a: float | None = None
    last_acknowledged_current_a: float | None = None
    last_command_at: str | None = None
    last_success_at: str | None = None
    last_command_result: str = "not_tested"
    last_command_error: str | None = None
    consecutive_failures: int = 0
    pending_current_a: float | None = None
    pending_enabled: bool | None = None
    pending_since: str | None = None
    next_retry_at: str | None = None

    @staticmethod
    def _parse(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def as_dict(self) -> dict:
        return asdict(self)

    def mark_observe_only(self) -> None:
        if self.status == "not_tested":
            self.status = "observe_only"
            self.last_command_result = "observe_only"

    def can_attempt(self, now: datetime, *, safety_stop: bool = False) -> bool:
        """Return whether a new service call may be issued.

        Safety stops bypass the ordinary command interval in the coordinator,
        but never bypass an in-flight acknowledgement or retry backoff.
        """
        retry = self._parse(self.next_retry_at)
        if retry is not None and now < retry:
            return False
        return self.pending_since is None

    def begin(
        self,
        now: datetime,
        *,
        requested_current_a: float | None = None,
        requested_enabled: bool | None = None,
    ) -> None:
        self.last_command_at = now.isoformat()
        if requested_current_a is not None:
            self.last_requested_current_a = requested_current_a
            self.pending_current_a = requested_current_a
        if requested_enabled is not None:
            self.pending_enabled = requested_enabled
        self.pending_since = now.isoformat()
        self.status = "awaiting_acknowledgement"
        self.last_command_result = "issued"
        self.last_command_error = None

    def record_failure(self, now: datetime, error: Exception | str) -> None:
        self.last_command_at = now.isoformat()
        self.healthy = False
        self.status = "command_failed"
        self.last_command_result = "failed"
        self.last_command_error = str(error)
        self.consecutive_failures += 1
        delay_s = min(300, 15 * (2 ** min(self.consecutive_failures - 1, 5)))
        self.next_retry_at = (now + timedelta(seconds=delay_s)).isoformat()
        self.pending_current_a = None
        self.pending_enabled = None
        self.pending_since = None

    def observe(
        self,
        now: datetime,
        *,
        current_a: float | None,
        physical_charging: bool,
        deadband_a: float,
        acknowledgement_timeout_s: float,
    ) -> str | None:
        """Reconcile commands against current and physical charger evidence.

        The charger's enable-switch state is deliberately not used: Smappee can
        report that switch as off while EVCC status and power prove charging.
        """
        if self.pending_since is None:
            return None
        current_ok = self.pending_current_a is None or (
            current_a is not None
            and abs(current_a - self.pending_current_a) < max(deadband_a, 0.05)
        )
        enabled_ok = (
            self.pending_enabled is None
            or physical_charging == self.pending_enabled
        )
        if current_ok and enabled_ok:
            self.healthy = True
            self.status = "acknowledged"
            self.last_command_result = "acknowledged"
            self.last_command_error = None
            self.last_success_at = now.isoformat()
            self.consecutive_failures = 0
            self.next_retry_at = None
            if self.pending_current_a is not None:
                self.last_acknowledged_current_a = current_a
            self.pending_current_a = None
            self.pending_enabled = None
            self.pending_since = None
            return "acknowledged"

        pending = self._parse(self.pending_since)
        if (
            pending is not None
            and (now - pending).total_seconds() >= acknowledgement_timeout_s
        ):
            self.record_failure(now, "Charger command acknowledgement timed out")
            return "failed"
        return None

    def cancel_pending_for_reduction(self, requested_current_a: float) -> None:
        """Allow a safer reduction to supersede a pending higher command."""
        if (
            self.pending_current_a is not None
            and requested_current_a < self.pending_current_a
        ):
            self.pending_current_a = None
            self.pending_enabled = None
            self.pending_since = None

    def cancel_pending_current(self, reason: str = "cancelled_by_policy") -> None:
        """Cancel a no-longer-needed current request but retain a stop ack."""
        if self.pending_current_a is None:
            return
        self.pending_current_a = None
        if self.pending_enabled is None:
            self.pending_since = None
            self.status = reason
            self.last_command_result = reason
