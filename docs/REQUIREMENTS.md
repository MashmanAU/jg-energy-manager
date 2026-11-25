# v0.3.3 requirement traceability

| Requirement | Implementation / gate |
|---|---|
| Preserve post-peak, floor pacing, deadline recovery and maximum allowance policy | Existing deterministic planner and A/B/C ten-minute simulations retained |
| Avoid transient post-peak start/stop cycling | Above-minimum requests step down to 6 A first; minimum-current hold requires measured headroom sufficient to cover excess import and expires after a configurable grace period |
| Stop promptly when the battery cannot respond | Immediate stop at/above the configurable 4.5 kW discharge ceiling, when residual headroom is insufficient, or when battery-power telemetry is invalid |
| Peak solar-overflow precedence | Genuine no-grid solar branch evaluated before peak stop; dedicated regression test |
| Observational Available Solar vs Calculated Power | Separate observed power-balance excess and policy EV request fields/tests |
| Accurate connection boundary | Rising edge establishes baseline and skips retrospective integration |
| Restart/stale boundary | Stale intervals are never integrated; valid cumulative meter remains authoritative |
| Meter outage/recovery/rollback | Bounded integration fallback and no-jump rebase tests |
| Charging-state early-full detection | Configured `charging_states`, prior-charge evidence, low-demand timeout and freeze tests |
| Last-session semantics | Persistent energy, unused allowance, start/end, satisfaction and end reason |
| Migration-safe metadata | Stable unique IDs; remaining allowance uses measurement state class without incompatible energy device class |
| Recorder churn | Rounded public current/power/energy values, minute completion and frozen satisfied energy |
| Resilient live actuation | Service exception containment, acknowledgement, bounded backoff, no enable-before-current-ack and failed-stop notification |
| Stale-off Smappee switch | Physical charging = charging status OR power above idle; stop and acknowledgement use physical evidence, not displayed switch state |
| Prompt reconciliation | State-change listeners for charger and energy inputs plus control changes and regular cycles |
| Restart/reload source snapshot | Direct full state-machine snapshot on first refresh, reload and every regular/event-driven cycle |
| Zero-safe conversion | Numeric `0`/`0.0`, status `A` and switch `off` remain valid input values |
| Actionable input health | Exact required missing/invalid role names, with entity IDs redacted, in diagnostics/logs/Input Problem attributes |
| Actuator diagnostics | Problem binary sensor, last acknowledged current/result/error and expanded redacted diagnostics |
| Config flow compatibility | v2 migration, charging-state field, Probatio serialisation and released HACS archive flow |
| Charger 2 exclusion | `parked_no_active_control`; no second actuator path |
| Release compatibility | Normal suite, metadata checks, actuator/session tests, policy simulations and real Home Assistant released-archive test |
