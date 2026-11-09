# Licensing scope

This note describes the current implementation and distribution. It is not a license for software owned by other projects.

| Component | License / treatment |
|---|---|
| Traffic Orb's original Swift/Python code, illustrations and skill | [MIT](../LICENSE) |
| v2rayN | [GPL-3.0](https://github.com/2dust/v2rayN/blob/master/LICENSE); used as a separately installed application, not bundled or modified here |
| Xray-core | [MPL-2.0](https://github.com/XTLS/Xray-core/blob/main/LICENSE); used as a separately running metrics source, not bundled or modified here |
| CPython runtime in release packages | PSF license and historical notices, copied into `licenses/Python-LICENSE.txt` |
| PyInstaller bootloader and loader | GPL-2.0-or-later with the bootloader exception; copied into `licenses/PyInstaller-COPYING.txt` |
| PyInstaller runtime hooks / additional runtime modules | Apache-2.0, included in the same PyInstaller license file |

## The automatic-recovery feature

Traffic Orb independently implements local HTTP metrics reading, endpoint caching, and discovery of loopback listeners associated with the user's running Xray process. It does not copy v2rayN/Xray source code or link their implementation into the app. Reading a separate application's statistics interface does not, by itself, mean this original code must adopt that application's license.

The PyInstaller exception expressly permits distributing combinations containing its compiled bootloader without the bootloader imposing GPL restrictions on the other program. Its runtime hooks have their own Apache-2.0 terms; the combined license text is retained in releases. See [PyInstaller's licensing terms](https://pyinstaller.org/en/stable/license.html) and [Python's license](https://docs.python.org/3/license.html).

## What distributors need to preserve

- Keep the MIT copyright and permission notice with Traffic Orb source or substantial copies.
- Keep the bundled runtime license notices with binary packages. Dependencies retain their own licenses; MIT does not replace those terms.
- Do not describe this as an official v2rayN/Xray product.
- If a future version copies upstream code, modifies upstream files or bundles upstream executables, review the applicable GPL/MPL distribution and source-availability obligations for those components before publishing.

The current Apple Silicon package links its standard-library extensions to macOS-provided system libraries; it does not contain separate copies of those system libraries. Different build environments can package different native dependencies, so new builds still require a dependency and notice check.
