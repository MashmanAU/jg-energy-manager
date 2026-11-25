# JG Energy Manager v0.3.4 — Release Candidate

**Status: validation candidate only — not approved for installation or live charger control.**

This repository package is supplied so it can be pushed to GitHub and the mandatory repository gates can execute in the pinned environment.

Do not install the integration or enable live controller operation unless both of the following GitHub Actions complete successfully for the exact source and tag being installed:

1. **Validate** — including the released HACS archive flow under Python 3.14, Home Assistant 2026.11.2 and Probatio.
2. **Release** — including the same released-archive gate, tag/manifest verification and release-asset publication.

A locally generated archive or a red/absent GitHub workflow result is not approval for commissioning. After both workflows are green, retain Observe Only during final site checks, remove the temporary helper automation, verify charger mappings and signs, and confirm actuator acknowledgement before enabling live control.

## Local release-candidate validation

- 77 deterministic planner, configuration, actuator, session, metadata and policy tests passed.
- Package validation, Python compilation, JSON parity, sensitive-file checks, release archive construction and duplicate/legacy-schema archive checks passed.
- The supplied `history (2).csv` contained 135 transitions between `deadline_recovery` and `impossible_target`, including 67 impossible-target entries. Reconstructing the buffered-deadline boundary showed entry deficits of approximately 0.001-0.020 kWh, well below the new 0.20 kWh default entry margin. A regression test retains a representative consecutive 10-second sequence from that pattern and confirms it no longer enters `impossible_target` or steps down from 32 A.
- Existing regressions still confirm immediate fine-grained post-peak current reductions and the v0.3.3 battery-headroom-aware 6 A hold/stop behaviour.

The pinned Home Assistant 2026.11.2 released-archive test requires the GitHub workflow environment and remains a mandatory external release gate.
