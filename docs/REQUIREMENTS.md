# v0.1.7 requirement traceability

| Requirement | Implementation |
|---|---|
| Smart Smappee charger, 6-32 A variable current | Charger status/power/energy/enable/current mappings; minimum, maximum, step and power cap in UI; bounded writes in `coordinator.py` |
| Overnight deadline-aware slow charging | `planner.py` calculates the lowest stepped current projected to deliver remaining maximum energy by ready-by time |
| Configurable maximum target energy | Schedule option; session baseline and delivered/remaining diagnostics |
| AlphaESS may fall to initial 10% overnight floor | 10% default and `overnight_floor` state; AlphaESS remains read-only and its native minimum-SOC logic remains authoritative |
| Daytime solar surplus and peak reserve | Export-feedback calculation, start/run margins, configurable SOC reserve and hysteresis |
| 3-9 pm peak protection | Configurable start/end and months; supplied tariff defaults to Jan-Mar, Jun-Aug and Nov-Dec |
| Observe Only / Dry Run | Persisted switch suppresses every actuator call while retaining calculations |
| Future second dumb charger | Name, on/off switch, status and power fields in config/options; diagnostic state; no v0.1.7 automatic writes |
| All mappings and logic configurable in UI | Multi-step config flow plus options menu for energy, charger, schedule, limits, control and secondary charger |
| Diagnostic explanation | State, reason, requested current/power, required/solar power, delivered/remaining energy, projected completion/deadline and health entities |
| No AlphaESS write control | Coordinator has no battery service-call path; battery entities are read-only |
| Private GitHub one-command publication | `publish.ps1`, deterministic validators/builders and tag-driven GitHub Actions release |
