# Changelog

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
