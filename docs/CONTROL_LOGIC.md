# Control logic - v0.3.3

## Safety and session boundaries

The energy target is a maximum per plug-in session, not a mandatory vehicle requirement. Disconnect, reset, invalid input and vehicle no-demand/full handling remain fail-safe. When the vehicle stops accepting power before the allowance is used, all deadline recovery stops. Observe Only continues calculations and diagnostics but sends no commands.

Every setup, reload, scheduled cycle and event-driven refresh reads a complete snapshot directly from the Home Assistant state machine. A state-change event is an acceleration signal, not the source of truth. Numeric zero, disconnected status `A` and switch `off` remain valid states. Required missing/invalid roles cause fail-safe stop and are named—without entity IDs—in diagnostics, logs and the Input Problem entity.

## Buffered deadline

The operational deadline is the ready-by time minus the configurable completion buffer. The planner continuously checks maximum physical deliverability. It reports `impossible_target` when maximum current cannot deliver the remaining allowance by that deadline. It reports `deadline_recovery` when grid-supported charging must begin now to retain feasibility.

Genuine no-grid solar overflow takes precedence during the peak window. Otherwise charging remains stopped when the remaining allowance still fits after peak. Peak import is requested only when deferring until peak end would make the buffered deadline infeasible.

## Post-peak and overnight battery policy

After peak, while battery SOC is above the overnight floor, the controller starts at minimum current and increases by the configured ramp step after each increase dwell. Grid-import feedback continues to cause fast, fine-grained current reductions so house load retains priority.

Stopping is evaluated separately from current tuning. If feedback would take the EV below the charger minimum, an active rate above 6 A is reduced to 6 A first. At 6 A, the controller calculates dependable battery headroom as the configured discharge control ceiling (4.5 kW by default) less measured battery discharge. It holds 6 A for the configured grace period only when that headroom can plausibly absorb all import above the grid tolerance. It stops immediately when battery discharge is at/above the ceiling, residual headroom cannot cover the import, battery-power telemetry is invalid, or the grace period expires. Any recovery to a supportable current cancels the hold timer.

At the overnight floor, the remaining allowance is spread over all time to the buffered deadline. The lowest continuous charger rate that preserves feasibility is requested, subject to minimum current, maximum current and charger power limits.

## Daytime battery priority

Below the daytime reserve, the battery receives priority up to the configured maximum battery charge rate. The EV receives only genuine overflow inferred from solar, grid and battery power; it is reduced or stopped on grid import or battery discharge.

At or above reserve, EV charging has priority over further battery charging. Current battery charging may be redirected to the EV, but grid import and battery discharge reduce the EV target. Increases are deliberately slow; decreases are fast.

**Available Solar Power** is observational power-balance excess before policy margins and reserve allocation. **Calculated Power** is the bounded power actually proposed by policy. This keeps monitoring truthful while retaining conservative charger control.

## Session accounting

The cumulative charger energy meter is authoritative. The integration establishes its baseline on the first connected sample and never backdates the current power across the connection edge or a stale/restart gap. Bounded power integration is used only while the meter is unavailable; meter recovery rebases to the fallback total without a jump. A meter rollback similarly rebases without losing delivered energy.

Early-full detection requires confirmed active charging during the session followed by a configured connected-but-not-charging state, low demand and the no-demand timeout while the controller is still requesting charge. Vehicle-delivered energy then freezes until disconnection. At disconnection the active values become unavailable and a persistent last-session summary is retained.

## Live actuator boundary

Current and enable services are issued only after deadband, dwell and command-interval checks. A current command must be observed on the writable current entity before an idle charger is enabled. Physical charging is derived from configured charging status **or** connector power above the idle threshold; the Smappee enable-switch display is not treated as authoritative.

A start acknowledges only after physical status/power confirms charging. A stop is issued whenever physical charging remains active—even if the switch already displays off—and acknowledges only when status is no longer charging **and** connector power is at or below idle. Vehicle/status, power, current, switch and energy-input changes request prompt reconciliation, supplemented by regular control cycles. Service failures and missing acknowledgements set actuator health, retain the planner output, and retry with bounded exponential backoff. Failed safety-stop commands also create a persistent notification.

## Operating modes

- **Automatic** - complete battery, solar, peak and buffered-deadline policy.
- **Force Charge** - configured force current, bounded by electrical limits and session/full safety.
- **Solar Only** - genuine no-grid, no-battery-discharge charging only; deadline recovery is disabled.
- **Off** - stop charging.

## Explicitly excluded from v0.3.3

There is no site import-limit controller, AlphaESS write control or automatic second-charger actuation. Charger 2 remains parked with diagnostic mappings only.
