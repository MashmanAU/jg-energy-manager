# Changelog

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
