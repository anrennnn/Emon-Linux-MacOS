"""Rutas y ajustes compartidos."""

import json
import os
import sys
from pathlib import Path

APP_ID = "emojis-linux"
APP_NAME = "Emojis"
VERSION = "0.1.0"

# Como en Windows, la sección «Usados recientemente» guarda unos pocos.
RECENT_LIMIT = 40

DATA_FILES = Path(__file__).resolve().parent / "datos"

IS_MACOS = sys.platform == "darwin"


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    return Path(value) if value else Path.home() / fallback


if IS_MACOS:
    DATA_DIR = CONFIG_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
else:
    DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share") / APP_ID
    CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config") / APP_ID
SETTINGS_FILE = DATA_DIR / "ajustes.json"
SHORTCUTS_MARKER = CONFIG_DIR / "atajos-configurados"


def session_type() -> str:
    """'wayland', 'x11' o 'macos'."""
    if IS_MACOS:
        return "macos"
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return "wayland"
    return "x11"


def desktop() -> str:
    """Escritorio normalizado: kde, gnome, cinnamon, xfce u otro."""
    raw = (os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "").lower()
    for name in ("kde", "cinnamon", "xfce", "gnome", "mate", "cosmic", "hyprland", "sway", "niri", "wayfire", "river"):
        if name in raw:
            return name
    # Pop!_OS, Zorin y Ubuntu usan variantes de GNOME ("pop:GNOME", "zorin:GNOME", "ubuntu:GNOME").
    if "unity" in raw or "budgie" in raw:
        return "gnome"
    return raw or "desconocido"


class Settings:
    """Emojis recientes y tono de piel elegido, guardados entre sesiones."""

    def __init__(self):
        self.recent: list[str] = []
        self.tone = 0  # 0 = amarillo (sin tono), 1..5 = de claro a oscuro
        self.shortcuts: list[str] = []  # vacío = los predeterminados; texto de Qt, p. ej. «Meta+.»
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            self.recent = [s for s in data.get("recientes", []) if isinstance(s, str)][:RECENT_LIMIT]
            self.tone = int(data.get("tono", 0)) if 0 <= int(data.get("tono", 0)) <= 5 else 0
            self.shortcuts = [s for s in data.get("atajos", []) if isinstance(s, str) and s]
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def use(self, text: str):
        self.recent = [text, *(s for s in self.recent if s != text)][:RECENT_LIMIT]
        self.save()

    def set_tone(self, tone: int):
        self.tone = tone
        self.save()

    def set_shortcuts(self, keys: list[str]):
        self.shortcuts = keys
        self.save()

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"recientes": self.recent, "tono": self.tone, "atajos": self.shortcuts}, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(SETTINGS_FILE)
