# Configuration reference

All values are editable in Home Assistant under the integration's **Configure** action.

## Energy inputs

- Battery SOC entity (required)
- Battery power entity and sign convention (optional; diagnostic in v0.1.7)
- Grid power entity and sign convention (required)
- Solar power entity (required)

## Smart charger

- Status sensor (required)
- Power sensor in W (required)
- Cumulative energy sensor in kWh (required)
- Enable switch or input boolean (required)
- Writable current number or input number in A (required)
- Comma-separated connected states (default `B,C`)

The charger entity pickers are intentionally not filtered by Home Assistant domain. This avoids rejecting compatible third-party charger entities in the configuration form. Select these Smappee Connector 1 entities: **EVCC state**, **Power**, **Energy import**, **EVCC charging**, and **Charging current limit**.

## Schedule and protection defaults

| Setting | Default |
|---|---:|
| Maximum session energy | 30 kWh |
| Ready by | 06:00 |
| Overnight start | 21:00 |
| Peak protection | 15:00-21:00 |
| Peak months | Jan-Mar, Jun-Aug, Nov-Dec |
| Overnight battery floor | 10% |
| Daytime battery reserve | 45% |
| SOC hysteresis | 2% |

## Electrical and solar defaults

| Setting | Default |
|---|---:|
| Minimum / maximum current | 6 A / 32 A |
| Maximum charger power | 7,360 W |
| Current step | 0.1 A |
| Supply | 230 V, 1 phase |
| Charging efficiency | 90% |
| Solar start margin | 400 W |
| Solar run margin | 150 W |
| Idle/no-demand threshold | 250 W |

## Controller defaults

| Setting | Default |
|---|---:|
| Control interval | 30 s |
| No-demand timeout | 180 s |
| Current command deadband | 0.2 A |
| Minimum command interval | 30 s |
| Stop when controller disabled | Yes |
| Fail-safe stop on invalid input | Yes |
| Initial Observe Only | Yes |

## Second charger

The name, on/off switch, status and power sensor are configurable now so the data model does not need to be migrated later. The v0.1.7 diagnostic state is `reserved_for_future_logic`; no automatic command is issued to this switch.
