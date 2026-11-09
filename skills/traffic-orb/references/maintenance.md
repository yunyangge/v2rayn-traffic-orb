# Maintenance notes

The public repository is https://github.com/yunyangge/v2rayn-traffic-orb. Source consists of a Swift AppKit UI, a small NSWorkspace lifecycle listener and a Python collector frozen into a standalone executable.

Use isolated `TRAFFIC_ORB_HOME`, `TRAFFIC_ORB_CONFIG` and `TRAFFIC_ORB_PORT` values for tests. Never read production node secrets into fixtures. The source README documents the build; use matching Swift/SDK versions and run the counter/quota tests before packaging.

Preserve these invariants:

- No external telemetry; HTTP listens only on loopback and checks Host.
- Quota = proxy upload + download; direct traffic is separate. No double counting of inbound and outbound.
- Reset counters and process changes must not yield negative rates or huge synthetic deltas.
- Daily boundaries use the local calendar; downtime limits recovery accuracy and must be disclosed.
- Settings saves are atomic; configuration and history live outside the `.app` so upgrades retain them.
- Menus use a separate panel clamped to the current screen, not a popup clipped by the tiny orb. UI remains responsive during alerts.
- The launch listener never starts v2rayN itself or changes its nodes/routes.
- Do not include runtime data, personal screenshots, build credentials or signing keys in releases.
