# JG Energy Manager

> **v0.3.3 release-candidate notice:** this source is not approved for installation or live controller operation until the GitHub **Validate** and **Release** workflows are green for the exact commit/tag. See [RELEASE_CANDIDATE.md](RELEASE_CANDIDATE.md).

A Home Assistant custom integration for deadline-aware EV charging and home-battery-aware solar charging. Version **0.3.3** is designed for a single smart Smappee EV charger with a writable **6-32 A** current setpoint and read-only AlphaESS inputs.

> **Safety default:** the integration starts in **Observe Only** mode. It calculates and exposes every proposed action, but does not write to the charger until Observe Only is explicitly turned off.

## v0.3.3 scope

- Post-peak battery-following EV charging without sustained grid import.
- Fast post-peak current reductions with battery-headroom-aware 6 A hold/stop control to avoid unnecessary charger contactor cycling.
- Buffered-deadline pacing and explicit recovery/impossible-target diagnostics.
- Battery-priority daytime overflow below reserve and EV-priority solar above reserve.
- Maximum session energy allowance with early-full detection.
- Automatic, Force Charge, Solar Only and Off modes.
- Observe Only commissioning and complete UI configuration.
- Acknowledged live actuation with bounded retry/backoff and visible actuator health.
- Physical start/stop reconciliation from EVCC status and connector power, independent of a stale Smappee switch display.
- Unconditional full input snapshots on setup, reload and every cycle, with zero-safe conversion and exact role-level health diagnostics.
- Accurate meter-first session accounting, frozen early-full energy and retained last-session results.

See [Control logic](docs/CONTROL_LOGIC.md) and [configuration](docs/CONFIGURATION.md).

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
| Charger status | **EVCC state** - Home Charger \| Connector 1 |
| Charger power | **Power** - Home Charger \| Connector 1 |
| Charger energy | **Energy import** - Home Charger \| Connector 1 |
| Charger enable | **EVCC charging** - Home Charger \| Connector 1 |
| Charger current | **Charging current limit** - Home Charger \| Connector 1 |

Do **not** select `Home Charger Connector 1 Maximum current` as the writable control. The charging-current-limit entity is the dynamic setpoint, while maximum current is the fixed installation ceiling.

Default connected status values are `B,C`; active charging values are `C,charging`. Both are editable in the integration options.

## First commissioning

1. Complete setup with **Start in Observe Only mode** enabled.
2. Connect a vehicle and leave Observe Only on while checking the live input signs and proposed daytime-solar calculation.
3. Verify:
   - **Controller reason** matches the expected window;
   - **Calculated current** stays between 6 A and 32 A;
   - **Grid import** is positive in the diagnostics (change the sign option if not);
   - session energy increases while charging;
    - peak protection calculates an off command between 3 pm and 9 pm unless genuine solar overflow is available;
    - **Available solar power** shows observed excess, while **Calculated power** shows the policy-controlled EV allocation;
    - **Actuator problem** is off.
4. Test the Smappee switch and charging-current number manually in Home Assistant.
5. Disable or delete the temporary helper automation so there is only one writer to the charger.
6. Turn **Observe Only** off. The **Live control active** binary sensor should turn on.
7. Keep the **Operating mode** select on **Automatic** for daytime solar excess and overnight operation.

## Controller priority

The automatic priority is deliberately deterministic:

1. Disabled, Off, disconnected, full/satisfied, maximum allowance reached or invalid input -> safe stop.
2. Force Charge -> configured manual current, bounded by electrical limits.
3. Solar Only -> no-grid and no-battery-discharge charging only.
4. Automatic peak window -> use genuine solar overflow first; otherwise stop unless charging is physically required for deadline feasibility.
5. Post-peak above the battery floor -> battery-following maximum without sustained import.
6. At the floor -> continuously pace the remainder to the buffered deadline.
7. Daytime -> battery-priority overflow below reserve, then EV-priority no-grid solar above reserve.

See [Control logic](docs/CONTROL_LOGIC.md) for formulas, edge cases and the session model, and [v0.3.3 requirement traceability](docs/REQUIREMENTS.md) for scope coverage.

## Entities created

### Controls

- `switch.*_controller_enabled`
- `switch.*_observe_only`
- `select.*_override` (`automatic`, `force_charge`, `solar_only`, `off`)
- `button.*_reset_charging_session`

### Diagnostics

- Controller state and reason
- Calculated current and power
- Required average power and observational available solar power
- Energy delivered this session and remaining session energy allowance
- Last-session energy, unused allowance, start/end and end reason
- Projected completion and current deadline
- Vehicle connected, vehicle charging, live control active, input problem and actuator problem
- Last acknowledged current and charger command result
- Second charger state (`parked_no_active_control`)

## Configuration changes

Every mapping, time, SOC threshold, current/power setting, margin, control interval and safety behaviour is editable under:

**Settings > Devices & services > JG Energy Manager > Configure**

Changes reload the integration; no new app version is required.

## Publication

From Windows PowerShell:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\publish.ps1" -RepositoryPath "C:\path\to\jg-energy-manager"
```

The script validates versions and JSON, compiles Python, runs tests, scans for likely secrets, builds release ZIPs, commits changes, tags `v0.3.3`, and pushes `main` plus the tag to `https://github.com/MashmanAU/jg-energy-manager.git`. Use `-NoPush` for a local validation/package run.

## Important limitations

- **No AlphaESS write control:** battery SOC and optional battery power are read-only inputs.
- **No vehicle SOC:** the session target is an upper bound, not a known vehicle requirement.
- **Second charger:** configuration only; no automatic actuation in v0.3.3.
- **Single controller instance per charger:** do not run EVCC or another automation against the same Smappee enable/current entities at the same time.
- This software controls charging equipment through Home Assistant. Commission in Observe Only mode and confirm electrical limits against the charger installation.
