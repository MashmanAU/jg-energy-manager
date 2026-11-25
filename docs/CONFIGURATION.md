# Configuration reference

All mappings and policy values are editable under the integration's **Configure** action.

## Energy inputs

- Battery SOC entity (required)
- Battery power entity and sign convention (strongly recommended for overflow and no-discharge control)
- Grid power entity and sign convention (required)
- Solar power entity (required)

## Smart charger

Use the Smappee Connector 1 entities **EVCC state**, **Power**, **Energy import**, **EVCC charging** and **Charging current limit**. Connected states default to `B,C`; active charging states default to `C,charging`. The latter must positively identify charging so early-full detection cannot be caused by a failed command or an idle connected vehicle.

Do not retain an automation that writes Calculated Current after live control is commissioned. The integration must be the sole writer to the enable and current entities so its acknowledgement, deadband, dwell and retry protections remain effective.

## Schedule and protection defaults

| Setting | Default |
|---|---:|
| Maximum session allowance | 30 kWh |
| Ready by | 06:00 |
| Completion buffer | 30 min |
| Overnight/post-peak start | 21:00 |
| Peak protection | 15:00-21:00 |
| Peak months | Jan-Mar, Jun-Aug, Nov-Dec |
| Overnight battery floor | 10% |
| Daytime battery reserve | 45% |
| SOC hysteresis | 2% |

## Electrical, feedback and solar defaults

| Setting | Default |
|---|---:|
| Minimum / maximum current | 6 A / 32 A |
| Force Charge current | 32 A |
| Maximum charger power | 7,360 W |
| Battery maximum charge rate | 5,000 W |
| Battery discharge control ceiling | 4,500 W |
| Grid tolerance | 100 W |
| Charger current step | 0.1 A |
| Slow-increase step | 1 A |
| Supply | 230 V, 1 phase |
| Charging efficiency | 90% |
| Solar start / run margins | 400 W / 150 W |
| Idle/no-demand threshold | 250 W |

## Control defaults

| Setting | Default |
|---|---:|
| Control interval | 30 s |
| No-demand timeout | 180 s |
| Current command deadband | 0.2 A |
| Minimum command interval | 30 s |
| Increase dwell | 120 s |
| Decrease dwell | 0 s |
| Battery response grace | 30 s |
| Stop when disabled | Yes |
| Fail-safe stop | Yes |
| Initial Observe Only | Yes |

## Second charger

Charger 2 remains parked with no active control logic. Turning the reserved feature off clears its switch, status and power mappings.
