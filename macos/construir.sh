#!/bin/sh
# Construye dist/Emon-<versión>-macOS-<arquitectura>.dmg. Hay que ejecutarlo en un Mac
# con Python 3.10 o más reciente (python.org o Homebrew). GitHub Actions lo hace solo.
set -eu
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' src/emon/config.py)
ARCH=$(uname -m)
PYTHON=${PYTHON:-python3}

rm -rf build/macos dist/Emon.app dist/Emon
mkdir -p build dist
"$PYTHON" -m venv build/macos/venv
. build/macos/venv/bin/activate
pip install -q --upgrade pip
pip install -q -r macos/requirements.txt

# Icono: SVG → iconset → .icns
python macos/hacer_icono.py data/icons/emon.svg build/macos/Emon.iconset
iconutil -c icns build/macos/Emon.iconset -o build/Emon.icns

pyinstaller --noconfirm --clean --distpath dist --workpath build/macos/pyinstaller macos/Emon.spec

# .dmg con la app y un acceso directo a Aplicaciones para arrastrarla.
STAGE=build/macos/dmg
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R dist/Emon.app "$STAGE/"
ln -s /Applications "$STAGE/Aplicaciones"
DMG="dist/Emon-$VERSION-macOS-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "Emon" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Listo: $DMG"
