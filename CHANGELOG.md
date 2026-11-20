# Changelog

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
