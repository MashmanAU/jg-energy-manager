# Changelog

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
