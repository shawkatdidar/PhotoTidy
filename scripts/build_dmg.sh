#!/bin/bash
# Builds dist/PhotoTidy-<version>.dmg from dist/Photo Tidy.app (run build_app.sh first).
# Optional notarization (needs an Apple Developer account): NOTARY_PROFILE=<notarytool keychain profile>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"
APP="$ROOT/dist/Photo Tidy.app"
DMG="$ROOT/dist/PhotoTidy-$VERSION.dmg"
[ -d "$APP" ] || { echo "Run scripts/build_app.sh first"; exit 1; }
codesign --verify --deep --strict "$APP" || { echo "App signature is invalid; rebuild it"; exit 1; }

if [ -n "${NOTARY_PROFILE:-}" ]; then
  SIGNATURE="$(codesign -dv --verbose=4 "$APP" 2>&1)"
  if [[ "$SIGNATURE" != *"Authority=Developer ID Application:"* || "$SIGNATURE" != *"runtime"* ]]; then
    echo "Notarization needs an app signed with Developer ID Application and hardened runtime."
    echo "Rebuild with SIGN_IDENTITY before running this script."
    exit 1
  fi
fi

STAGE="$(mktemp -d)/Photo Tidy"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
if [ -n "${NOTARY_PROFILE:-}" ]; then
  cp "$ROOT/scripts/FIRST_OPEN_NOTARIZED.txt" "$STAGE/Read me first.txt"
else
  cp "$ROOT/scripts/FIRST_OPEN.txt" "$STAGE/Read me first.txt"
fi
rm -f "$DMG"
hdiutil create -volname "Photo Tidy" -srcfolder "$STAGE" -fs HFS+ -format UDZO -imagekey zlib-level=9 -ov "$DMG" >/dev/null
if [ -n "${NOTARY_PROFILE:-}" ]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
  xcrun stapler validate "$DMG"
fi
(cd "$ROOT/dist" && shasum -a 256 "PhotoTidy-$VERSION.dmg") | tee "$DMG.sha256"
ls -lh "$DMG"
