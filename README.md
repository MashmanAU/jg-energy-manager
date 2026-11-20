# JG Energy Manager

A Home Assistant custom integration for deadline-aware EV charging and home-battery-aware solar charging. Version **0.1.0** is designed for a single smart Smappee EV charger with a writable **6-32 A** current setpoint and read-only AlphaESS inputs.

> **Safety default:** the integration starts in **Observe Only** mode. It calculates and exposes every proposed action, but does not write to the charger until Observe Only is explicitly turned off.

## v0.1.0 scope

- Overnight slow charging paced to a configurable maximum session energy and ready-by time.
- AlphaESS may support overnight charging down to a configurable battery floor (default 10%). The integration does **not** write to AlphaESS.
- Daytime charging uses measured export headroom and protects a configurable battery reserve for the 3-9 pm peak.
- Seasonal peak-period automatic charging protection, defaulting to 3-9 pm in Jan-Mar, Jun-Aug and Nov-Dec.
- Configurable 6-32 A limits, maximum charger power, voltage, phases, margins, update intervals, deadbands, entity mappings and status mappings.
- Session energy tracked from the charger's cumulative energy sensor, with power integration as a fallback.
- A 30 kWh target is treated as an **upper bound**. If the vehicle stops accepting power after 11 kWh, the controller stops trying after a configurable no-demand timeout.
- Observe Only, controller enable and manual Force Off / Force Maximum overrides.
- Diagnostic entities explain controller state, reason, current/power request, delivered/remaining energy and projected completion.
- Second on/off-only charger fields are stored in the data model and options UI, but automatic Charger 2 control is intentionally deferred.

## Installation

### HACS (private custom repository)

1. In HACS, add `https://github.com/MashmanAU/jg-energy-manager` as a **Custom repository** of type **Integration**. Authenticate GitHub for the private repository when prompted.
2. Install **JG Energy Manager**.
3. Restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration**, search for **JG Energy Manager**, and complete the wizard.

### Manual

Copy `custom_components/jg_energy_manager` into Home Assistant's `/config/custom_components/` directory and restart Home Assistant.

## Recommended entity mapping

Choose entities by friendly name because the Smappee device serial forms part of some generated entity IDs.

| JG Energy Manager field | Recommended source |
|---|---|
| Battery SOC | AlphaESS state-of-charge sensor (%) |
| Battery power (optional) | AlphaESS battery power sensor; select its sign convention |
| Grid power | Smappee grid power sensor; select whether positive means import |
| Solar power | Smappee production/solar power sensor |
| Charger status | Smappee connector EVCC state sensor (A/B/C) |
| Charger power | `Home Charger Connector 1 Power` sensor |
| Charger energy | Cumulative connector imported-energy sensor |
| Charger enable | Smappee connector charging switch |
| Charger current | **`Home Charger Connector 1 Charging current`** number (writable setpoint) |

Do **not** select `Home Charger Connector 1 Maximum current` as the writable control. The screenshots and diagnostics show the charging-current entity is the dynamic setpoint, while maximum current is the fixed installation ceiling.

Default connected status values are `B,C,connected,charging,suspended_ev` and can be edited in the integration options.

## First commissioning

1. Complete setup with **Start in Observe Only mode** enabled.
2. Connect a vehicle and leave Observe Only on for at least one overnight and one solar period.
3. Verify:
   - **Controller reason** matches the expected window;
   - **Calculated current** stays between 6 A and 32 A;
   - **Grid import** is positive in the diagnostics (change the sign option if not);
   - session energy increases while charging;
   - peak protection calculates an off command between 3 pm and 9 pm.
4. Test the Smappee switch and charging-current number manually in Home Assistant.
5. Turn **Observe Only** off. The **Live control active** binary sensor should turn on.
6. Keep the **Override** select on **Automatic** for normal operation.

## Controller priority

The automatic priority is deliberately deterministic:

1. Invalid critical input -> fail-safe stop (configurable).
2. Controller disabled / Force Off / no vehicle / vehicle satisfied / target reached -> stop.
3. Force Maximum -> explicit manual override, including peak.
4. Configured 3-9 pm seasonal peak window -> stop.
5. Overnight window -> pace remaining maximum energy to the ready-by deadline.
6. Other times -> charge only from stable export headroom while preserving the daytime battery reserve.

See [Control logic](docs/CONTROL_LOGIC.md) for formulas, edge cases and the session model, and [v0.1.0 requirement traceability](docs/REQUIREMENTS.md) for scope coverage.

## Entities created

### Controls

- `switch.*_controller_enabled`
- `switch.*_observe_only`
- `select.*_override` (`automatic`, `force_off`, `force_max`)
- `button.*_reset_charging_session`

### Diagnostics

- Controller state and reason
- Calculated current and power
- Required average power and available solar power
- Energy delivered this session and maximum energy remaining
- Projected completion and current deadline
- Vehicle connected, live control active and input problem
- Second charger state (`not_configured` or `reserved_for_future_logic`)

## Configuration changes

Every mapping, time, SOC threshold, current/power setting, margin, control interval and safety behaviour is editable under:

**Settings > Devices & services > JG Energy Manager > Configure**

Changes reload the integration; no new app version is required.

## Publication

From Windows PowerShell:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\publish.ps1" -RepositoryPath "C:\path\to\jg-energy-manager"
```

The script validates versions and JSON, compiles Python, runs tests, scans for likely secrets, builds release ZIPs, commits changes, tags `v0.1.0`, and pushes `main` plus the tag to `https://github.com/MashmanAU/jg-energy-manager.git`. Use `-NoPush` for a local validation/package run.

## Important limitations

- **No AlphaESS write control:** battery SOC and optional battery power are read-only inputs.
- **No vehicle SOC:** the session target is an upper bound, not a known vehicle requirement.
- **Second charger:** configuration only; no automatic actuation in v0.1.0.
- **Single controller instance per charger:** do not run EVCC or another automation against the same Smappee enable/current entities at the same time.
- This software controls charging equipment through Home Assistant. Commission in Observe Only mode and confirm electrical limits against the charger installation.
