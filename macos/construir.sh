#!/bin/sh
# Construye dist/Emojis-<versión>-macOS-<arquitectura>.dmg. Hay que ejecutarlo en un Mac
# con Python 3.10 o más reciente (python.org o Homebrew). GitHub Actions lo hace solo.
set -eu
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' src/emojis_linux/config.py)
ARCH=$(uname -m)
PYTHON=${PYTHON:-python3}

rm -rf build/macos dist/Emojis.app dist/Emojis
mkdir -p build dist
"$PYTHON" -m venv build/macos/venv
. build/macos/venv/bin/activate
pip install -q --upgrade pip
pip install -q -r macos/requirements.txt

# Icono: SVG → iconset → .icns
python macos/hacer_icono.py data/icons/emojis-linux.svg build/macos/Emojis.iconset
iconutil -c icns build/macos/Emojis.iconset -o build/Emojis.icns

pyinstaller --noconfirm --clean --distpath dist --workpath build/macos/pyinstaller macos/Emojis.spec

# .dmg con la app y un acceso directo a Aplicaciones para arrastrarla.
STAGE=build/macos/dmg
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R dist/Emojis.app "$STAGE/"
ln -s /Applications "$STAGE/Aplicaciones"
DMG="dist/Emojis-$VERSION-macOS-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "Emojis" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Listo: $DMG"
