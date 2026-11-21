# Changelog

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
