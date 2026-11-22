# Control logic - v0.2.0

## Safety and session boundaries

The energy target is a maximum per plug-in session, not a mandatory vehicle requirement. Disconnect, reset, invalid input and vehicle no-demand/full handling remain fail-safe. When the vehicle stops accepting power before the allowance is used, all deadline recovery stops. Observe Only continues calculations and diagnostics but sends no commands.

## Buffered deadline

The operational deadline is the ready-by time minus the configurable completion buffer. The planner continuously checks maximum physical deliverability. It reports `impossible_target` when maximum current cannot deliver the remaining allowance by that deadline. It reports `deadline_recovery` when grid-supported charging must begin now to retain feasibility.

Peak charging remains stopped when the remaining allowance still fits after peak. Peak import is requested only when deferring until peak end would make the buffered deadline infeasible.

## Post-peak and overnight battery policy

After peak, while battery SOC is above the overnight floor, the controller starts at minimum current and increases by the configured ramp step after each increase dwell. Grid-import feedback causes a fast reduction or pause, allowing house load to take priority while finding the highest stable battery-supported EV rate.

At the overnight floor, the remaining allowance is spread over all time to the buffered deadline. The lowest continuous charger rate that preserves feasibility is requested, subject to minimum current, maximum current and charger power limits.

## Daytime battery priority

Below the daytime reserve, the battery receives priority up to the configured maximum battery charge rate. The EV receives only genuine overflow inferred from solar, grid and battery power; it is reduced or stopped on grid import or battery discharge.

At or above reserve, EV charging has priority over further battery charging. Current battery charging may be redirected to the EV, but grid import and battery discharge reduce the EV target. Increases are deliberately slow; decreases are fast.

## Operating modes

- **Automatic** - complete battery, solar, peak and buffered-deadline policy.
- **Force Charge** - configured force current, bounded by electrical limits and session/full safety.
- **Solar Only** - genuine no-grid, no-battery-discharge charging only; deadline recovery is disabled.
- **Off** - stop charging.

## Explicitly excluded from v0.2.0

There is no site import-limit controller, AlphaESS write control or automatic second-charger actuation. Disabled second-charger mappings are cleared.
