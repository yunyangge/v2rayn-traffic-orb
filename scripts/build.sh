#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ARCH="$(uname -m)"
PYTHON="${BUILD_PYTHON:-python3}"
SDK="${SDKROOT:-$(xcrun --show-sdk-path)}"
STAGE="$ROOT/.build/TrafficOrb-$ARCH"
APP="$STAGE/TrafficOrb.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$ROOT/dist"
cp packaging/Info.plist "$APP/Contents/Info.plist"
cp resources/default-settings.json "$APP/Contents/Resources/default-settings.json"
printf '%s\n' "$ARCH" > "$APP/Contents/Resources/architecture.txt"
xcrun swiftc -sdk "$SDK" -target "$ARCH-apple-macosx13.0" -O \
  src/Paths.swift src/QuotaPolicy.swift src/MenuLayout.swift src/TrafficOrb.swift \
  -framework Cocoa -o "$APP/Contents/MacOS/TrafficOrb"
xcrun swiftc -sdk "$SDK" -target "$ARCH-apple-macosx13.0" -O \
  src/Paths.swift src/LifecycleWatcher.swift -framework Cocoa \
  -o "$APP/Contents/MacOS/LifecycleWatcher"
"$PYTHON" -m PyInstaller --noconfirm --clean --onefile --noupx \
  --name TrafficOrbCollector --target-arch "$ARCH" --osx-bundle-identifier app.trafficorb.collector \
  --workpath "$ROOT/.build/pyinstaller" --specpath "$ROOT/.build" \
  --distpath "$APP/Contents/MacOS" --add-data "$ROOT/resources:assets" src/collector.py
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
ditto skills "$STAGE/skills"
mkdir -p "$STAGE/scripts"
cp scripts/install.sh scripts/uninstall.sh scripts/install-skill.sh "$STAGE/scripts/"
cp packaging/Install.command packaging/Uninstall.command packaging/Install-Skill.command "$STAGE/"
cp README.md LICENSE THIRD_PARTY_NOTICES.md "$STAGE/"
"$PYTHON" scripts/copy_runtime_licenses.py "$STAGE/licenses"
chmod +x "$STAGE/"*.command "$STAGE/scripts/"*.sh
TEST_HOME="$(mktemp -d)"
TRAFFIC_ORB_HOME="$TEST_HOME" "$APP/Contents/MacOS/TrafficOrb" --check-package
rm -rf "$TEST_HOME"
"$PYTHON" tests/smoke_release.py "$APP/Contents/MacOS/TrafficOrbCollector"
"$PYTHON" scripts/privacy_check.py "$STAGE"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$STAGE" "$ROOT/dist/TrafficOrb-macOS-$ARCH.zip"
(cd dist && shasum -a 256 "TrafficOrb-macOS-$ARCH.zip" > "TrafficOrb-macOS-$ARCH.zip.sha256")
printf 'Built: %s\n' "$ROOT/dist/TrafficOrb-macOS-$ARCH.zip"
