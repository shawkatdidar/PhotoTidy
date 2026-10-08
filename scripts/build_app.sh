#!/bin/bash
# Builds dist/Photo Tidy.app: a self-contained app (own Python + dependencies, native window, icon).
# Requirements: Apple Silicon Mac, Xcode Command Line Tools (swiftc), uv (brew install uv).
# Optional: SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" to sign with your own certificate.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/Photo Tidy.app"
RES="$APP/Contents/Resources"
PYVER="${PYVER:-3.12}"
VERSION="$(cat "$ROOT/VERSION")"
IDENTITY="${SIGN_IDENTITY:--}"

[ "$(uname -m)" = "arm64" ] || { echo "Apple Silicon required"; exit 1; }
command -v uv >/dev/null || { echo "uv is required: brew install uv"; exit 1; }
command -v swiftc >/dev/null || { echo "swiftc is required: xcode-select --install"; exit 1; }

echo "==> Preparing bundle"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$RES/app"

echo "==> Bundling Python $PYVER"
uv python install "$PYVER" >/dev/null
PYBIN="$(uv python find "$PYVER")"
PYROOT="$(dirname "$(dirname "$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$PYBIN")")")"
cp -R "$PYROOT" "$RES/python"
rm -f "$RES"/python/lib/python*/EXTERNALLY-MANAGED
BUNDLED="$(ls "$RES"/python/bin/python3.* | head -1)"

echo "==> Installing dependencies"
uv pip install --python "$BUNDLED" --compile-bytecode -r "$ROOT/requirements.txt" -q

echo "==> Trimming"
find "$RES/python/bin" -mindepth 1 ! -name "python3" ! -name "python3.[0-9]*" -delete
rm -f "$RES"/python/bin/*-config
rm -rf "$RES/python/include" "$RES/python/share"
LIB="$(ls -d "$RES"/python/lib/python3.*)"
rm -rf "$LIB"/test "$LIB"/idlelib "$LIB"/tkinter "$LIB"/turtledemo "$LIB"/ensurepip "$LIB"/lib2to3 "$LIB"/config-* \
       "$LIB"/site-packages/pip "$LIB"/site-packages/pip-* "$LIB"/lib-dynload/_tkinter* "$RES"/python/lib/tcl* "$RES"/python/lib/tk* \
       "$RES"/python/lib/itcl* "$RES"/python/lib/thread* "$RES"/python/lib/libtcl* "$RES"/python/lib/libtk* "$RES"/python/lib/pkgconfig \
       "$LIB"/site-packages/jedi "$LIB"/site-packages/jedi-* "$LIB"/site-packages/parso "$LIB"/site-packages/parso-* "$LIB"/site-packages/PyObjCTest
find "$LIB/site-packages" -type d \( -name tests -o -name test \) -prune -exec rm -rf {} +

install_name_tool -id @rpath/libpython3.12.dylib "$RES/python/lib/libpython3.12.dylib" 2>/dev/null || true

echo "==> App code"
rsync -a --exclude __pycache__ "$ROOT/photo_tidy" "$RES/app/"
"$BUNDLED" -m compileall -q -j 0 "$RES/app" "$LIB/site-packages" >/dev/null || true

echo "==> Native host"
swiftc -O -swift-version 5 -target arm64-apple-macos13.0 "$ROOT/app/main.swift" \
  -framework Cocoa -framework WebKit -framework Photos -o "$APP/Contents/MacOS/PhotoTidy"
sed "s/@VERSION@/$VERSION/g" "$ROOT/app/Info.plist" > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"
TMP="$(mktemp -d)"
"$BUNDLED" "$ROOT/scripts/make_icon.py" "$TMP/AppIcon.icns" 2>/dev/null || python3 "$ROOT/scripts/make_icon.py" "$TMP/AppIcon.icns"
cp "$TMP/AppIcon.icns" "$RES/AppIcon.icns"

echo "==> Signing ($([ "$IDENTITY" = "-" ] && echo ad-hoc || echo "$IDENTITY"))"
OPTS=(--force --sign "$IDENTITY")
[ "$IDENTITY" != "-" ] && OPTS+=(--options runtime --timestamp --entitlements "$ROOT/app/entitlements.plist")
# Sign every nested Mach-O first. A failed nested signature must stop the release.
while IFS= read -r -d '' f; do
  codesign "${OPTS[@]}" "$f"
done < <(find "$RES/python" -type f \( -name "*.so" -o -name "*.dylib" -o -path "*/python/bin/*" \) -print0)
codesign "${OPTS[@]}" "$APP"
codesign --verify --deep --strict "$APP" && echo "signature OK"
du -sh "$APP"
