---
name: traffic-orb
description: Install, configure, diagnose, or maintain the macOS Traffic Orb widget for v2rayN/Xray, including daily quota alerts and launch/exit linkage. Use for Traffic Orb requests; not for VPN node provisioning or server administration.
---

# Traffic Orb

Operate the installed local widget or a supplied release/source folder. Establish the user's requested scope before changing it; installation, quota editing and diagnostics do not imply permission to change VPN nodes, route rules or publish logs.

## Find the installation

The normal app is `~/Applications/TrafficOrb.app`, data is `~/Library/Application Support/TrafficOrb`, and the lifecycle LaunchAgent is `~/Library/LaunchAgents/app.trafficorb.lifecycle.plist`. Resolve the current user's home at runtime. An environment override or user-selected directory takes precedence.

For installation, use a matching macOS release ZIP and its `Install.command`/`scripts/install.sh`. Read the archive README first. The app includes its collector runtime; do not ask the user to install Python merely to run it. `Install-Skill.command` installs this optional skill. Do not remove quarantine attributes or disable Gatekeeper; use normal macOS opening/approval flows if required.

## Configure or diagnose

- Prefer right-click → 设置每日限额. The setting is decimal GB, 0.1–1,000,000. Alerts at 80%, 95%, 100% do not cut the network. Existing usage must remain intact.
- When a direct file change is appropriate, atomically edit only `daily_limit_gb` in `settings.json`, preserving other keys. The collector rereads it without restart.
- Check process and loopback health at `http://127.0.0.1:18863/health`, then `/api/stats`; diagnostics should report status and counts only. The bundled `TrafficOrbCollector --diagnose` is a credential-safe first check.
- If metrics are disabled, guide the user to enable statistics / real-time speed in v2rayN and restart its service. Do not dump `config.json`, subscription URLs, UUIDs, passwords, server addresses or full logs into chat. Ask before a disruptive client restart unless already authorized.
- Xray and sing-box are different backends. Do not report zero usage when the current core is unsupported or disconnected.
- A closed v2rayN window may leave its process running. The widget follows the process. A manually quit widget returns on the next v2rayN launch.
- To uninstall, use the release `Uninstall.command`. Preserve settings and history unless deletion is explicitly requested.

## Maintenance

Read [references/maintenance.md](references/maintenance.md) when rebuilding or debugging lifecycle/counter behavior. Work from public source only. Keep test data isolated; do not overwrite an active installation during routine diagnostics. Before a requested publication, scan staged source and packaged content and exclude all real user data.
