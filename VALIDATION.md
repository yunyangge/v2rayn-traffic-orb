# Validation record

This record includes proxy-guard verification on 2026-11-12 and the earlier collector checks from 2026-11-09. It distinguishes local execution, simulated checks, and unverified platforms. It is not a claim that the GitHub Actions workflow has passed.

| Area | Evidence | Scope / limit |
|---|---|---|
| Native build | Swift UI and lifecycle helper compiled and code signatures verified | Apple Silicon, local macOS 26.6; deployment target macOS 13 |
| Bundle layout | Packaged App `--check-package` found its bundled collector and created isolated per-user settings | Temporary application-data directory; no production settings overwritten |
| Collector and guard logic | Seventeen `unittest` cases passed | Original counter/recovery checks plus route attribution, rolling persistence, threshold termination, proxy-only restart blocking, log rewriting and argument redaction |
| Guard accounting | Local prototype tested with small controlled connections through Xray | A 128 KiB direct-routed response was excluded; a proxy-routed response was counted. No GB-scale test transfer was generated |
| Guard termination | Isolated temporary `sleep` processes were stopped at the synthetic 5 GB boundary and on renewed proxy use | The direct-only restart stayed alive; system/other-user process termination is not claimed |
| Frozen guard | Packaged collector `--guard` produced status using a temporary Xray access log; a duplicate invocation exited without replacing the live PID | Isolated per-user state, default off, working singleton lock; not a clean-machine installation |
| Standalone runtime | Frozen collector served metrics, dashboard and health endpoint against a fake Xray server | No real VPN required; Host rejection and diagnostics output checked |
| Installation | App copying, paths with spaces, launch-agent plist generation, skill installation and uninstall checked | Temporary home directory; launchd was mocked, so this is not a clean-machine end-to-end installation |
| Data preservation | Mock install/uninstall left existing usage data intact | Configuration files are outside the App bundle |
| Native UI | Menu, positioning, quota validation/save/reopen, preview alerts and color display exercised in the local prototype | Same application logic; not a fresh third-party Mac test |
| Process linkage | Local prototype followed real v2rayN startup/exit and kept daily counts | Distributable installer launchd binding has only the isolated script check above |
| Privacy | Public source, release contents and decompressed collector scanned; compared against local private identifiers without printing them | No runtime logs, history, subscriptions or node credentials included; does not substitute for a complete security audit |
| Intel | Build workflow and source path provided | No Intel release binary or real-device validation yet |
| Cloud CI | Workflow exists | No successful hosted build recorded for this change; local arm64 v1.1.0 build only, no new release published |
| Signing | ad-hoc signature verification passed | No Apple Developer ID notarization |

## Reproduce the automated checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/privacy_check.py .
```

`python3` above refers to the build environment with `requirements-build.txt` installed. The build script also runs the frozen collector smoke test before creating the ZIP.

The source and runtime allow testing with `TRAFFIC_ORB_HOME`, `TRAFFIC_ORB_CONFIG` and `TRAFFIC_ORB_PORT`; see [development.md](docs/development.md). Keep test data separate from the installed application's data.
