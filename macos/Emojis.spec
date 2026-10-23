# PyInstaller: construye dist/Emojis.app. Se usa desde macos/construir.sh.
import os
import re

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")
with open(os.path.join(SRC, "emojis_linux", "config.py"), encoding="utf-8") as fh:
    VERSION = re.search(r'^VERSION = "(.*)"', fh.read(), re.M).group(1)

a = Analysis(
    [os.path.join(SPECPATH, "emojis.py")],
    pathex=[SRC],
    datas=[(os.path.join(SRC, "emojis_linux", "datos"), "emojis_linux/datos")],
    hiddenimports=[
        "emojis_linux.macos", "emojis_linux.picker", "emojis_linux.catalog",
        "emojis_linux.inserter", "AppKit", "Quartz",
    ],
    excludes=["tkinter", "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtWebEngineCore", "PyQt6.QtMultimedia"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Emojis",
    console=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Emojis")
app = BUNDLE(
    coll,
    name="Emojis.app",
    icon=os.path.join(ROOT, "build", "Emojis.icns"),
    bundle_identifier="io.github.anrennnn.emojis",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "Emojis",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSUIElement": True,  # sin icono en el Dock: es un panel, como el de Windows
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "MIT. Datos de emojis © Unicode, Inc.",
    },
)
