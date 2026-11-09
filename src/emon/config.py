"""Rutas y ajustes compartidos."""

import json
import os
import sys
from pathlib import Path

APP_ID = "emon"
APP_NAME = "Emon"
VERSION = "0.3.0"

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

# Hasta la 0.2 la app se llamaba «Emojis» (paquete y comando emojis-linux).
OLD_ID = "emojis-linux"
if IS_MACOS:
    OLD_DATA_DIRS = [Path.home() / "Library" / "Application Support" / "Emojis"]
else:
    OLD_DATA_DIRS = [_xdg("XDG_DATA_HOME", ".local/share") / OLD_ID, _xdg("XDG_CONFIG_HOME", ".config") / OLD_ID]


def migrate_old_settings() -> bool:
    """Trae los ajustes de «Emojis» (recientes, tono, atajo) la primera vez. True si había."""
    if SETTINGS_FILE.exists():
        return False
    for folder in OLD_DATA_DIRS:
        old = folder / "ajustes.json"
        if old.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_bytes(old.read_bytes())
            return True
    return False


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
        # Acción → atajos, texto de Qt (p. ej. «Meta+.»). Si falta una acción, sus
        # atajos son los predeterminados; una lista vacía significa «sin atajo».
        self.bindings: dict[str, list[str]] = {}
        self.legacy_shortcuts = False  # venían de la lista única de la 0.3 o anterior
        self.keyboard_token = ""  # permiso del portal RemoteDesktop (Wayland) para no volver a pedirlo
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            self.recent = [s for s in data.get("recientes", []) if isinstance(s, str)][:RECENT_LIMIT]
            self.tone = int(data.get("tono", 0)) if 0 <= int(data.get("tono", 0)) <= 5 else 0
            stored = data.get("atajos_acciones")
            if isinstance(stored, dict):
                self.bindings = {
                    str(action): [s for s in keys if isinstance(s, str) and s]
                    for action, keys in stored.items()
                    if isinstance(keys, list)
                }
            else:
                # Hasta la 0.3 solo había una lista de atajos, todos para abrir el panel.
                legacy = [s for s in data.get("atajos", []) if isinstance(s, str) and s]
                if legacy:
                    self.bindings = {"abrir": legacy}
                    self.legacy_shortcuts = True
            self.keyboard_token = str(data.get("permiso_teclado", ""))
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    @property
    def shortcuts(self) -> list[str]:
        """Compatibilidad: atajos de «abrir» (vacío = los predeterminados)."""
        return list(self.bindings.get("abrir", []))

    def use(self, text: str):
        self.recent = [text, *(s for s in self.recent if s != text)][:RECENT_LIMIT]
        self.save()

    def set_tone(self, tone: int):
        self.tone = tone
        self.save()

    def set_keyboard_token(self, token: str):
        self.keyboard_token = token
        self.save()

    def set_bindings(self, bindings: dict[str, list[str]]):
        self.bindings = {action: list(keys) for action, keys in bindings.items()}
        self.save()

    def set_shortcuts(self, keys: list[str]):
        """Compatibilidad: cambia solo los atajos de «abrir»."""
        self.set_bindings({**self.bindings, "abrir": list(keys)})

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "recientes": self.recent,
                    "tono": self.tone,
                    # Se sigue escribiendo «atajos» para que una versión anterior
                    # de Emon conserve al menos el atajo del panel.
                    "atajos": self.bindings.get("abrir", []),
                    "atajos_acciones": self.bindings,
                    "permiso_teclado": self.keyboard_token,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        tmp.replace(SETTINGS_FILE)
