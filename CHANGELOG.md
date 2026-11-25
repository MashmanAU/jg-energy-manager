# Changelog

## 0.3.4 - 2026-11-26

- Added deadline-feasibility hysteresis: `impossible_target` now requires a configurable 0.20 kWh deficit and remains latched until a configurable 0.25 kWh achievable-energy margin is restored.
- Made maximum deadline output sticky: after reaching maximum, the controller releases only when calculated current remains at least 2 A below maximum for 60 seconds.
- Kept the new dwell isolated from ordinary battery/grid feedback so fast fine-grained current reductions and all v0.3.3 battery-headroom-aware 6 A stop logic remain unchanged.
- Added diagnostics for feasibility margin, impossible-target latch, maximum-output hold and release dwell.
- Added regression coverage distilled from the supplied `history (2).csv` 10-second `deadline_recovery` / `impossible_target` oscillation.

## 0.3.3 - 2026-11-25

- Kept rapid post-peak load tuning and immediate fine-grained current reductions while separating minimum-current stopping from ordinary current adjustment.
- Changed below-minimum feedback to reduce an active charger to 6 A before considering a complete stop.
- Added a configurable 4.5 kW battery discharge control ceiling and a 30-second battery response grace period.
- At 6 A and above the overnight SOC floor, hold charging only when measured battery headroom can plausibly absorb all grid import above tolerance; stop immediately when the battery is at/above the ceiling or residual headroom is insufficient.
- Disabled the grace path when battery-power telemetry is unavailable or invalid, and exposed hold status, available headroom, uncovered import and timer start in diagnostics.
- Added deterministic regressions for step-down-before-stop, credible-headroom hold, grace expiry, near-ceiling stop, insufficient-headroom stop and invalid-telemetry stop.

## 0.3.2 - 2026-11-23

- Fixed the v0.3.1 numeric-input regression that displaced the float-conversion block and caused every valid numeric Home Assistant state, including zero, to resolve as null after restart/reload.
- Added an unconditional full snapshot of every configured live input on first setup refresh, reload, every regular control cycle and every event-driven refresh; sampling never depends on a prior state-change callback.
- Added explicit required/optional role health with exact missing and invalid role names in redacted diagnostics, Input Problem attributes and transition-only logs.
- Preserved numeric zero, disconnected EVCC state `A` and enable state `off` as valid source states.
- Added startup/reload regressions using valid pre-existing Home Assistant states with no later events, plus unavailable-to-valid recovery and optional-input degradation coverage.
- Preserved the v0.3.1 physical start/stop reconciliation, bounded retries/backoff, failed-stop notification, all v0.3.0 policy/session fixes, parked Charger 2 and Home Assistant 2026.11.2 release gates.

## 0.3.1 - 2026-11-23

- Reconciled charger start/stop acknowledgement from physical evidence: configured charging status or connector power above the idle threshold, independent of the Smappee enable switch display.
- Stop now calls `switch.turn_off` whenever physical charging remains active, even when the enable switch already reports off, and acknowledges only after status is non-charging and power is at or below idle.
- Start now requires writable-current acknowledgement before `switch.turn_on`, then acknowledges only from physical status/power evidence.
- Added event-driven reconciliation for vehicle/status, connector power, current, switch and energy-system input changes in addition to regular control cycles and explicit control-state changes.
- Preserved bounded acknowledgement timeout, retry/backoff and failed-stop notification, all v0.3.0 policy/session fixes, parked Charger 2 and the Home Assistant 2026.11.2 released-archive gates.
- Added regressions for the confirmed stale-off switch behaviour and controlled 6 A B→C/~1.4 kW start and C→B/0 W stop sequence.

## 0.3.0 - 2026-11-23

- Restored migration-safe measurement metadata for Remaining Session Energy Allowance while preserving the established unique ID and historical statistics continuity.
- Made cumulative charger energy authoritative, removed connection-edge and restart backdating, added bounded integration fallback/recovery, and froze vehicle-delivered energy at satisfaction.
- Added persistent last-session energy, unused allowance, start/end, satisfaction and end-reason semantics.
- Added acknowledged live actuation, bounded retry/backoff, command-health entities, failed-stop notification and protection against enabling before current acknowledgement.
- Applied configured charging states to early-full detection and exposed connected-versus-charging diagnostics.
- Confirmed genuine solar overflow precedence during tariff peaks and separated observational Available Solar Power from policy-controlled Calculated Power.
- Rounded public sensor values and projected completion to reduce recorder churn without reducing control precision.
- Expanded redacted diagnostics with effective configuration, session accounting source, input health and actuator acknowledgement details.
- Kept Charger 2 parked with no active control logic and preserved all v0.2.0 policy, config-flow, released-archive and deterministic simulation gates.

## 0.2.0 - 2026-11-22

- Added post-peak battery-following control that ramps toward the highest stable EV rate without sustained grid import and reduces quickly around house loads.
- Added buffered-deadline pacing at the overnight battery floor, explicit deadline recovery and impossible-target diagnostics, including peak charging only when physically required.
- Kept the configured session energy as a maximum allowance and retained unused battery energy when the vehicle becomes full early.
- Added battery-priority daytime overflow capture below reserve and EV-priority no-grid solar charging above reserve using grid and battery power feedback.
- Added Automatic, Force Charge, Solar Only and Off operating modes, with configurable Force Charge current.
- Added battery maximum charge rate, grid tolerance, ramp-up step, increase/decrease dwell and completion-buffer settings to the Home Assistant UI.
- Removed the invalid measurement state class from Maximum Energy Remaining and clear dormant second-charger mappings when disabled.
- Added deterministic ten-minute simulations for the agreed 30 kWh/high-SOC, 30 kWh/low-SOC and 10 kWh early-full scenarios.
- Preserved the released-HACS-archive Home Assistant 2026.11.1/Probatio config-flow gate and all v0.1.7 compatibility fixes.

## 0.1.7 - 2026-11-22

- Fixed the Home Assistant 2026.11.1/Probatio 0.13.0 Limits failure caused by passing `unit_of_measurement=None` to `NumberSelectorConfig` for charging efficiency.
- Changed the number-selector helper to omit `unit_of_measurement` entirely for unitless fields while retaining real unit strings for current, power, voltage, percentages and time values.
- Audited every selector helper and config construction for optional parameters explicitly supplied as `None`; no other instances remain.
- Added local regression checks, archive AST validation and real Home Assistant assertions that optional selector keys are absent rather than null.
- Preserved the v0.1.6 peak-months removal, schema diagnostics and mandatory released-HACS-archive test through config-entry creation.

## 0.1.6 - 2026-11-22

- Confirmed from the Home Assistant Core traceback that the reproduced failure was Probatio serialising a Schedule schema containing the legacy `_peak_months` callable.
- Confirmed the supplied traceback occurred at 10:42, before the logged Home Assistant restarts at 13:31, 14:31 and 23:14; the v0.1.5 repository and HACS archives contain `TextSelector()` in the Schedule schema and cannot create that specific callable-validator result.
- Removed the legacy `_peak_months` symbol entirely to make stale-code identification unambiguous while retaining post-submit month normalisation.
- Added pre-return Probatio serialisation checks and explicit exception logging for every schema, Schedule, Limits and step transitions.
- Added deterministic Limits-default and JSON-serialisability checks.
- Added release-archive verification for duplicate files, legacy validator symbols, callable validators and Limits translations.
- Added a mandatory GitHub test using Home Assistant 2026.11.1 and its real Probatio serializer against the built `dist/jg_energy_manager.zip`, advancing every first-time setup form through config-entry creation.

## 0.1.5 - 2026-11-21

- Fixed the persistent Schedule submission failure occurring while Home Assistant serialised the next Limits form.
- Removed digit-only phase selector values (`"1"` and `"3"`) from the Home Assistant form boundary and replaced them with stable string tokens (`single_phase` and `three_phase`) translated as **1 phase** and **3 phases**.
- Kept canonical stored phase values as integers and retained compatibility with legacy integer and string phase values.
- Replaced remaining primitive text and boolean validators in rendered forms with official Home Assistant Text and Boolean selectors.
- Added a Home Assistant-compatible end-to-end flow harness that serialises and advances User, Energy, Charger, Schedule, Limits, Control and Secondary through config-entry creation, plus complete Options Flow rendering and Limits persistence coverage.
- Preserved all entity-selector, connected-state, peak-month and validation fixes through v0.1.4.

## 0.1.4 - 2026-11-21

- Fixed the Limits form rejecting the numeric stored/default phase value when its selector options are strings (`1` and `3`).
- Rendered phase defaults and suggested values as strings in both the initial Config Flow and Options Flow.
- Converted submitted phase selections back to integers before configuration or options storage.
- Added regression coverage for the Schedule-to-Limits transition, phase type conversion and Limits configuration in Options Flow.
- Preserved all config-flow, selector and validation corrections through v0.1.3.

## 0.1.3 - 2026-11-21

- Fixed Smart charger submission advancing into a Schedule form containing the remaining non-serialisable `peak_months` validator.
- Moved peak-month normalisation into the config and options step handlers, matching the v0.1.2 connected-state correction.
- Added field-level validation errors for invalid connected states and peak months instead of returning a generic flow error.
- Preserved the unfiltered Smart charger selectors and `B,C` connected-state handling from v0.1.1 and v0.1.2.
- Added regression coverage to prevent custom validators being embedded in Home Assistant form schemas.

## 0.1.2 - 2026-11-21

- Fixed the Energy inputs submission returning `Unknown error occurred` and then validating Energy fields against the Smart charger schema on a second submit.
- Replaced the non-serialisable connected-state form validator with Home Assistant's text selector and moved `B,C` normalisation into the config and options step handlers.
- Preserved the v0.1.1 unfiltered Smart charger entity selectors.
- Added regression tests for schema serialisation and connected-state normalisation in both config and options flows.

## 0.1.1 - 2026-11-21

- Fixed the Smart charger configuration step rejecting valid Home Assistant entity selections as "not a valid option".
- Removed strict domain filtering from charger entity pickers so compatible third-party charger entities can be selected.
- Normalised connected-state input and changed the Smappee default to `B,C`.
- Added regression tests for the charger schema and connected-state normalisation.

## 0.1.0 - 2026-11-21

- First installable Home Assistant custom integration.
- Added 6-32 A smart Smappee control, overnight deadline pacing, daytime export control, battery reserve/floor handling and peak protection.
- Added Observe Only, overrides, persistent session tracking and diagnostic entities.
- Added complete UI configuration and future second on/off charger model.
- Added tests, GitHub Actions, release packaging and one-command PowerShell publication.
