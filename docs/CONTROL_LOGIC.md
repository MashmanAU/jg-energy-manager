# Control logic - v0.1.0

## Normalised inputs

The coordinator reads battery SOC, grid power, solar power, charger state, charger power, cumulative charger energy, the charger enable switch and the writable current number. Grid power is normalised so **positive always means import**. Battery power is normalised so **positive always means discharge**; battery power is diagnostic only in v0.1.0.

Critical invalid inputs request a fail-safe stop when that option is enabled. No command is issued while Observe Only is on.

## Session energy

A new session begins on the disconnected-to-connected transition. The cumulative charger-energy value becomes the baseline. Delivered energy is:

```text
max(cumulative energy - session baseline, integrated charger power)
```

Power integration is a fallback and is capped to a five-minute sample gap. Runtime state is stored every five minutes and on control changes, allowing a Home Assistant restart to retain the current session.

The configured target is a **maximum session delivery**, not a claim that the car needs that energy. If the charger was requested on but power remains below the idle threshold for the no-demand timeout, the session becomes `vehicle_satisfied` and the controller stops. Unplugging resets that latch.

## Overnight deadline controller

Within the overnight window:

```text
remaining_kWh = max(0, target_kWh - delivered_kWh)
required_input_W = remaining_kWh * 1000 / (hours_to_deadline * efficiency)
requested_A = ceil_to_step(required_input_W / (voltage * phases))
requested_A = clamp(requested_A, minimum_A, maximum_A)
```

This starts as early as the configured overnight window permits and uses the lowest current that still projects completion by the ready-by time, subject to the charger's minimum current. If the calculated current exceeds the configured maximum, the controller enters `deadline_recovery` and requests maximum current.

When battery SOC reaches the overnight floor, charging continues at the deadline rate. Because v0.1.0 does not write to AlphaESS, the inverter's own minimum-SOC behaviour is responsible for stopping further battery discharge and allowing grid supply for the shortfall.

## Daytime solar mode

Daytime start is gated by battery SOC. When off, SOC must exceed `reserve + hysteresis`; while running, it may continue down to `reserve - hysteresis`.

Stable power headroom is calculated from the grid meter and present EV load:

```text
available_W = max(0, charger_power_W - grid_import_W - margin_W)
requested_A = floor_to_step(available_W / (voltage * phases))
```

The larger start margin is used when the charger is off; the smaller run margin is used after it starts. If available power is below the minimum charger power, charging stops. This gives export-led control and avoids treating battery discharge as free solar headroom.

## Peak protection and overrides

The 3-9 pm window has priority over automatic overnight/daytime logic in the configured months. The default months (Jan-Mar, Jun-Aug and Nov-Dec) match the supplied seasonal tariff. It stops charging. `force_max` is an explicit user override and therefore takes priority over peak protection; `force_off` always stops.

## Command shaping

- Current is written before the charger is enabled.
- Current changes smaller than the current deadband are ignored.
- The minimum command interval prevents rapid setpoint/start calls; stop commands are never delayed.
- The enable switch is only called when its state needs to change.
- Observe Only suppresses all actuator calls while retaining identical calculations and diagnostics.
