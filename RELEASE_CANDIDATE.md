# JG Energy Manager v0.3.1 — Release Candidate

**Status: validation candidate only — not approved for installation or live charger control.**

This repository package is supplied so it can be pushed to GitHub and the mandatory repository gates can execute in the pinned environment.

Do not install the integration or enable live controller operation unless both of the following GitHub Actions complete successfully for the exact source and tag being installed:

1. **Validate** — including the released HACS archive flow under Python 3.14, Home Assistant 2026.11.2 and Probatio.
2. **Release** — including the same released-archive gate, tag/manifest verification and release-asset publication.

A locally generated archive or a red/absent GitHub workflow result is not approval for commissioning. After both workflows are green, retain Observe Only during final site checks, remove the temporary helper automation, verify charger mappings and signs, and confirm actuator acknowledgement before enabling live control.
