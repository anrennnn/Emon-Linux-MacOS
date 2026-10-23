"""Registra Super+. y Super+; (los dos atajos de Windows) en el escritorio del usuario.

Cada escritorio guarda sus atajos en un sitio distinto, así que no hay una única
forma de hacerlo. Se ejecuta una vez por usuario (al primer arranque) y se puede
repetir con `emojis-linux atajos`.
"""

import ast
import shutil
import subprocess

from . import config

OPEN_CMD = "emojis-linux abrir"
BINDINGS = ("<Super>period", "<Super>semicolon")


def _run(*cmd) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _gsettings_list(schema: str, key: str) -> list[str]:
    raw = _run("gsettings", "get", schema, key)
    raw = raw.removeprefix("@as ")
    try:
        value = ast.literal_eval(raw) if raw else []
    except (ValueError, SyntaxError):
        value = []
    return list(value)


def _gsettings_set(schema: str, key: str, value):
    if isinstance(value, list):
        value = "[" + ", ".join(repr(v) for v in value) + "]"
    _run("gsettings", "set", schema, key, value)


# --- GNOME (Ubuntu, Pop!_OS, Zorin, Fedora Workstation) ----------------------------

GNOME_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"


def _setup_gnome() -> list[str]:
    paths = _gsettings_list(GNOME_KEYS, "custom-keybindings")
    # GNOME solo admite una tecla por atajo personalizado: uno para cada combinación.
    for n, binding in enumerate(BINDINGS):
        path = f"{GNOME_BASE}emojis-linux-{n}/"
        if path not in paths:
            paths.append(path)
        schema = f"{GNOME_KEYS}.custom-keybinding:{path}"
        _gsettings_set(schema, "name", "Panel de emojis")
        _gsettings_set(schema, "command", OPEN_CMD)
        _gsettings_set(schema, "binding", binding)
    _gsettings_set(GNOME_KEYS, "custom-keybindings", paths)
    return []


# --- Cinnamon (Linux Mint) --------------------------------------------------------

CINNAMON_KEYS = "org.cinnamon.desktop.keybindings"
CINNAMON_BASE = "/org/cinnamon/desktop/keybindings/custom-keybindings/"


def _setup_cinnamon() -> list[str]:
    names = _gsettings_list(CINNAMON_KEYS, "custom-list")
    slug = "custom-emojis-linux"
    if slug not in names:
        names.append(slug)
    schema = f"{CINNAMON_KEYS}.custom-keybinding:{CINNAMON_BASE}{slug}/"
    _gsettings_set(schema, "name", "Panel de emojis")
    _gsettings_set(schema, "command", OPEN_CMD)
    _gsettings_set(schema, "binding", list(BINDINGS))
    _gsettings_set(CINNAMON_KEYS, "custom-list", names)
    return []


# --- XFCE (Xubuntu, MX Linux, Mint XFCE) ------------------------------------------


def _setup_xfce() -> list[str]:
    for binding in BINDINGS:
        _run(
            "xfconf-query", "-c", "xfce4-keyboard-shortcuts",
            "-p", f"/commands/custom/{binding}", "-n", "-t", "string", "-s", OPEN_CMD,
        )
    return []


# --- KDE Plasma (Kubuntu, KDE neon, Fedora KDE, CachyOS) ---------------------------

# Códigos de tecla de Qt, tal como los espera kglobalaccel.
_META, _CTRL, _ALT, _SHIFT = 0x10000000, 0x04000000, 0x08000000, 0x02000000
_KEY_PERIOD, _KEY_SEMICOLON, _KEY_SPACE = 0x2E, 0x3B, 0x20

# (componente, acción, teclas nuevas). El atajo de Emojis viene de la línea
# X-KDE-Shortcuts de emojis-linux.desktop; antes hay que quitárselo al selector de KDE.
KDE_CHANGES = [
    # El selector de emojis de Plasma usa Meta+. ; se le deja Meta+Ctrl+Alt+Mayús+Espacio.
    ("org.kde.plasma.emojier.desktop", "_launch", [_META | _CTRL | _ALT | _SHIFT | _KEY_SPACE]),
    ("emojis-linux.desktop", "_launch", [_META | _KEY_PERIOD, _META | _KEY_SEMICOLON]),
]


def _kglobalaccel_set(component: str, action: str, keys: list[int]) -> bool:
    """Cambia un atajo en caliente por D-Bus; kglobalaccel lo guarda por su cuenta."""
    if not shutil.which("gdbus"):
        return False
    sequences = ", ".join(f"([{k}, 0, 0, 0],)" for k in keys)
    try:
        subprocess.run(
            [
                "gdbus", "call", "--session", "--dest", "org.kde.kglobalaccel",
                "--object-path", "/kglobalaccel",
                "--method", "org.kde.KGlobalAccel.setForeignShortcutKeys",
                f"['{component}', '{action}', '', '']",
                f"@a(ai) [{sequences}]",
            ],
            capture_output=True, timeout=5, check=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _setup_kde() -> list[str]:
    if all(_kglobalaccel_set(*change) for change in KDE_CHANGES):
        return ["El selector de emojis de KDE pasa a Meta+Ctrl+Alt+Mayús+Espacio."]

    # kglobalaccel no responde: se deja escrito para el próximo inicio de sesión.
    writer = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if not writer:
        raise ShortcutError("No se pudo hablar con KDE; asigna el atajo en Preferencias del sistema → Atajos.")

    def write(groups, key, value):
        cmd = [writer, "--file", "kglobalshortcutsrc"]
        for g in groups:
            cmd += ["--group", g]
        _run(*cmd, "--key", key, value)

    write(["services", "org.kde.plasma.emojier.desktop"], "_launch", "Meta+Ctrl+Alt+Shift+Space")
    write(["services", "emojis-linux.desktop"], "_launch", "Meta+.\tMeta+;")
    return ["Cierra sesión y vuelve a entrar para activar Super+. en KDE Plasma."]


class ShortcutError(RuntimeError):
    pass


SETUP = {
    "gnome": _setup_gnome,
    "cinnamon": _setup_cinnamon,
    "xfce": _setup_xfce,
    "kde": _setup_kde,
}


# Gestores de ventanas en mosaico (habituales en Arch y CachyOS): los atajos viven en
# el archivo de configuración del usuario, que no tocamos; se indica qué añadir.
MANUAL = {
    "hyprland": ("~/.config/hypr/hyprland.conf", [f"bind = SUPER, period, exec, {OPEN_CMD}"]),
    "sway": ("~/.config/sway/config", [f"bindsym Mod4+period exec {OPEN_CMD}"]),
    "niri": ("~/.config/niri/config.kdl (dentro de binds { })", ['Mod+Period { spawn "emojis-linux" "abrir"; }']),
}


def setup_shortcuts(force: bool = False) -> list[str]:
    """Configura los atajos una sola vez. Devuelve mensajes para mostrar al usuario."""
    if config.SHORTCUTS_MARKER.exists() and not force:
        return []
    desktop = config.desktop()
    func = SETUP.get(desktop)
    if func is not None:
        try:
            notes = [f"Atajo configurado para {desktop}: Super+. (o Super+;) abre el panel de emojis.", *func()]
        except ShortcutError as exc:
            notes = [str(exc), f"  Super+. → {OPEN_CMD}"]
    elif desktop in MANUAL:
        path, lines = MANUAL[desktop]
        notes = [f"Añade esta línea a {path}:", *lines]
    else:
        notes = [f"Escritorio «{desktop}» no reconocido. Asigna a mano:", f"  Super+. → {OPEN_CMD}"]
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.SHORTCUTS_MARKER.write_text(desktop + "\n", encoding="utf-8")
    return notes
