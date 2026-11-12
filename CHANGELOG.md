# Changelog

## v1.1.0 — Unreleased (2026-11-12)

- Added opt-in proxy traffic protection in the orb menu: a configurable 5 GB default per-workload upload + download budget over a rolling hour.
- Classifies connections using Xray access-log outbound tags and attributes local proxy bytes to their source processes. Direct connections, metrics requests and the proxy's forwarding side are excluded.
- Terminates over-budget user processes, escalates if necessary, and blocks renewed proxy use by the same workload for one hour. Direct-only restarts remain allowed.
- Persists budgets and trigger records outside the app bundle. Missing routing evidence disables enforcement rather than guessing.
- Bundles the guard in the existing standalone runtime and starts/stops it through the lifecycle helper. Public installs default to protection off and do not edit v2rayN settings.
- Added guard tests and a frozen-runtime smoke test. Existing v1.0.1 release downloads do not include this feature.

## v1.0.1 — 2026-11-09

- Added automatic metrics recovery when v2rayN's generated `config.json` is removed or temporarily unavailable.
- Reuses a working loopback endpoint and can rediscover listeners belonging to the running v2rayN/Xray process. Other applications are not scanned.
- Preserves counter identity across recovery so existing daily usage is retained and available increments are recovered without restarting the proxy.
- Diagnostics distinguish an absent configuration file from an unreachable statistics endpoint.
- Added regression tests for missing configuration, collector restart, endpoint changes and address validation.
- Expanded bilingual documentation, usage illustrations, validation scope and licensing notes.

Recovery does not reconstruct traffic lost across an unobserved Xray restart, and does not bypass missing metrics support or disabled statistics.

## v1.0.0 — 2026-11-09

- Initial native macOS orb, daily quotas and reminders, lifecycle integration, standalone collector, installers and optional Codex skill.
