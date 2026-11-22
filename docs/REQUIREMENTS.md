# v0.2.0 requirement traceability

| Requirement | Implementation |
|---|---|
| Post-peak battery-supported maximum | Grid-feedback ramp with slow increases and fast import-driven decreases |
| Floor-to-deadline spreading | Buffered deadline and continuous required-average calculation |
| Maximum allowance / early full | Persistent session accounting and no-demand/full stop before mandatory recovery |
| Deadline feasibility | Peak-aware recovery, impossible-target state and diagnostic reasons |
| Battery-priority overflow | Grid + battery feedback and configured battery maximum charge rate |
| EV priority above reserve | Battery-charge reallocation with no grid import or battery discharge |
| Four operating modes | Automatic, Force Charge, Solar Only and Off |
| Observe Only | All calculations retained; actuator calls suppressed |
| Session and fail-safe handling | Disconnect/reset/full/input-loss handling retained |
| Exclusions | No site import limit, AlphaESS writes or active second charger |
| Metadata correction | Maximum Energy Remaining has no measurement state class |
| Configurability | All new policy values available in Config Flow and Options Flow |
| Scenario tests | Deterministic ten-minute A, B and C simulations |
| Release compatibility | Built HACS archive tested with Home Assistant 2026.11.1 and Probatio |
