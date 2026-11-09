"""Registra los atajos del panel en el escritorio.

Cada escritorio guarda sus atajos en un sitio distinto, así que no hay una única
forma de hacerlo. Se ejecuta al primer arranque, cuando el usuario cambia los
atajos en la ventana de ajustes y con `emon atajos`.

Cada acción (abrir el panel, abrir símbolos o abrir los ajustes) puede tener su
propio atajo. Se guardan como texto de Qt («Meta+.», «Ctrl+Alt+E»); en Linux
Meta es la tecla Super (la de Windows).
"""

import ast
import shutil
import subprocess

from . import actions, config

# Comandos que puede haber dejado Emon (los actuales y los de versiones anteriores).
OUR_COMMANDS = {action.command for action in actions.ACTIONS} | {
    "emojis-linux abrir", "emojis-linux simbolos", "emojis-linux ajustes",
}
# En macOS, Qt llama «Ctrl» a ⌘ y «Meta» a ⌃: el predeterminado es ⌃⌘. (⌘. es «cancelar»).
DEFAULT_KEYS = list(actions.ACTIONS_BY_ID["abrir"].defaults)

# Nombres de tecla de X11/xkb, los que usan GNOME, Cinnamon, XFCE, Hyprland y Sway.
_KEYSYMS = {
    ".": "period", ",": "comma", ";": "semicolon", ":": "colon", "'": "apostrophe", '"': "quotedbl",
    "/": "slash", "\\": "backslash", "[": "bracketleft", "]": "bracketright", "-": "minus", "=": "equal",
    "`": "grave", "+": "plus", "*": "asterisk", "#": "numbersign", "<": "less", ">": "greater",
    "Space": "space", "Return": "Return", "Enter": "Return", "Tab": "Tab", "Ins": "Insert", "Del": "Delete",
    "Home": "Home", "End": "End", "PgUp": "Prior", "PgDown": "Next", "Esc": "Escape",
}
_GTK_MODS = {"Meta": "<Super>", "Ctrl": "<Control>", "Alt": "<Alt>", "Shift": "<Shift>"}


def split(key: str) -> tuple[list[str], str]:
    """«Meta+Shift+.» → (['Meta', 'Shift'], '.'). La tecla «+» se escribe «Meta++»."""
    if key.endswith("++"):
        return [m for m in key[:-2].split("+") if m], "+"
    *mods, last = key.split("+")
    return mods, last


def keysym(name: str) -> str:
    if name in _KEYSYMS:
        return _KEYSYMS[name]
    return name.lower() if len(name) == 1 else name


def to_gtk(key: str) -> str:
    """«Meta+.» → «<Super>period»."""
    mods, name = split(key)
    return "".join(_GTK_MODS.get(m, "") for m in mods) + keysym(name)


def label(key: str) -> str:
    """Para enseñar al usuario: «Meta+.» → «Super+.»."""
    if config.IS_MACOS:
        from .qt import QKeySequence

        return QKeySequence(key).toString(QKeySequence.SequenceFormat.NativeText)
    mods, name = split(key)
    return " + ".join([*("Super" if m == "Meta" else m for m in mods), name])


def current_keys() -> list[str]:
    """Atajos de «abrir el panel», que es la acción imprescindible."""
    return actions.current(config.Settings())["abrir"]


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


def _setup_gnome(bindings: dict[str, list[str]], _old: dict[str, list[str]]) -> list[str]:
    # GNOME solo admite una tecla por atajo personalizado: uno para cada combinación.
    # Primero se quitan todos los de Emon, por si antes había más.
    paths = [
        p for p in _gsettings_list(GNOME_KEYS, "custom-keybindings")
        if "/emon-" not in p and "/emojis-linux-" not in p
    ]
    n = 0
    for action in actions.ACTIONS:
        for key in bindings.get(action.id, []):
            path = f"{GNOME_BASE}emon-{n}/"
            paths.append(path)
            schema = f"{GNOME_KEYS}.custom-keybinding:{path}"
            _gsettings_set(schema, "name", action.name)
            _gsettings_set(schema, "command", action.command)
            _gsettings_set(schema, "binding", to_gtk(key))
            n += 1
    _gsettings_set(GNOME_KEYS, "custom-keybindings", paths)
    return []


# --- Cinnamon (Linux Mint) --------------------------------------------------------

CINNAMON_KEYS = "org.cinnamon.desktop.keybindings"
CINNAMON_BASE = "/org/cinnamon/desktop/keybindings/custom-keybindings/"


def _setup_cinnamon(bindings: dict[str, list[str]], _old: dict[str, list[str]]) -> list[str]:
    names = [
        n for n in _gsettings_list(CINNAMON_KEYS, "custom-list")
        if not n.startswith("custom-emon") and n != "custom-emojis-linux"
    ]
    for action in actions.ACTIONS:
        keys = bindings.get(action.id, [])
        if not keys:
            continue
        slug = "custom-emon" if action.id == "abrir" else f"custom-emon-{action.id}"
        names.append(slug)
        schema = f"{CINNAMON_KEYS}.custom-keybinding:{CINNAMON_BASE}{slug}/"
        _gsettings_set(schema, "name", action.name)
        _gsettings_set(schema, "command", action.command)
        _gsettings_set(schema, "binding", [to_gtk(k) for k in keys])
    _gsettings_set(CINNAMON_KEYS, "custom-list", names)
    return []


# --- XFCE (Xubuntu, MX Linux, Mint XFCE) ------------------------------------------


def _setup_xfce(bindings: dict[str, list[str]], _old: dict[str, list[str]]) -> list[str]:
    # Quita cualquier atajo de Emon (los de ahora y los de la versión anterior),
    # sea cual sea la tecla a la que estuviera asignado.
    listing = _run("xfconf-query", "-c", "xfce4-keyboard-shortcuts", "-l", "-v")
    for line in listing.splitlines():
        prop, _, value = line.partition(" ")
        if value.strip() in OUR_COMMANDS:
            _run("xfconf-query", "-c", "xfce4-keyboard-shortcuts", "-p", prop, "-r")
    for action in actions.ACTIONS:
        for key in bindings.get(action.id, []):
            _run(
                "xfconf-query", "-c", "xfce4-keyboard-shortcuts",
                "-p", f"/commands/custom/{to_gtk(key)}", "-n", "-t", "string", "-s", action.command,
            )
    return []


# --- KDE Plasma (Kubuntu, KDE neon, Fedora KDE, CachyOS) ---------------------------

# Modificadores de Qt, tal como los espera kglobalaccel.
_META, _CTRL, _ALT, _SHIFT = 0x10000000, 0x04000000, 0x08000000, 0x02000000
_KEY_SPACE, _KEY_PERIOD = 0x20, 0x2E
EMOJIER = ("org.kde.plasma.emojier.desktop", "_launch")
# Nombre de la acción dentro de emon.desktop (ver data/applications/emon.desktop).
KDE_ACTIONS = {"abrir": "_launch", "simbolos": "simbolos", "ajustes": "ajustes"}


def _kde_code(key: str) -> int:
    from .qt import QKeySequence, combined

    return combined(QKeySequence(key))


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


def _setup_kde(bindings: dict[str, list[str]], old: dict[str, list[str]]) -> list[str]:
    notes = []
    # El atajo de la versión anterior («Emojis»); si nunca existió, el error da igual.
    _kglobalaccel_set("emojis-linux.desktop", "_launch", [])
    changes = [
        ("emon.desktop", KDE_ACTIONS[action.id], [_kde_code(k) for k in bindings.get(action.id, [])])
        for action in actions.ACTIONS
    ]
    uses_period = any("Meta+." in keys for keys in bindings.values())
    used_before = any("Meta+." in keys for keys in old.values())
    if uses_period:
        # El selector de emojis de Plasma usa Meta+. ; se le deja Meta+Ctrl+Alt+Mayús+Espacio.
        changes.insert(0, (*EMOJIER, [_META | _CTRL | _ALT | _SHIFT | _KEY_SPACE]))
        notes.append("El selector de emojis de KDE pasa a Meta+Ctrl+Alt+Mayús+Espacio.")
    elif used_before:
        # Emon deja libre Meta+.: se le devuelve al selector de KDE.
        changes.append((*EMOJIER, [_META | _KEY_PERIOD]))
    if all(_kglobalaccel_set(*change) for change in changes):
        return notes

    # kglobalaccel no responde: se deja escrito para el próximo inicio de sesión.
    writer = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if not writer:
        raise ShortcutError("No se pudo hablar con KDE; asigna los atajos en Preferencias del sistema → Atajos.")

    def write(groups, key, value):
        cmd = [writer, "--file", "kglobalshortcutsrc"]
        for g in groups:
            cmd += ["--group", g]
        _run(*cmd, "--key", key, value)

    if uses_period:
        write(["services", EMOJIER[0]], EMOJIER[1], "Meta+Ctrl+Alt+Shift+Space")
    for action in actions.ACTIONS:
        write(["services", "emon.desktop"], KDE_ACTIONS[action.id], "\t".join(bindings.get(action.id, [])))
    return [*notes, "Cierra sesión y vuelve a entrar para activar los atajos en KDE Plasma."]


class ShortcutError(RuntimeError):
    pass


SETUP = {
    "gnome": _setup_gnome,
    "cinnamon": _setup_cinnamon,
    "xfce": _setup_xfce,
    "kde": _setup_kde,
}


def _manual_lines(desktop: str, bindings: dict[str, list[str]]) -> tuple[str, list[str]] | None:
    """Gestores en mosaico (habituales en Arch y CachyOS): los atajos viven en el archivo
    de configuración del usuario, que no tocamos; se indica qué añadir."""
    lines = []
    for action in actions.ACTIONS:
        for key in bindings.get(action.id, []):
            mods, name = split(key)
            sym = keysym(name)
            if desktop == "hyprland":
                hypr = " ".join({"Meta": "SUPER", "Ctrl": "CTRL", "Alt": "ALT", "Shift": "SHIFT"}[m] for m in mods)
                lines.append(f"bind = {hypr}, {sym}, exec, {action.command}")
            elif desktop == "sway":
                sway = "+".join({"Meta": "Mod4", "Ctrl": "Ctrl", "Alt": "Mod1", "Shift": "Shift"}[m] for m in mods)
                lines.append(f"bindsym {sway}+{sym} exec {action.command}")
            elif desktop == "niri":
                niri = "+".join({"Meta": "Mod", "Ctrl": "Ctrl", "Alt": "Alt", "Shift": "Shift"}[m] for m in mods)
                lines.append(f'{niri}+{sym} {{ spawn "emon" "{action.id}"; }}')
    if not lines:
        return None
    path = {
        "hyprland": "~/.config/hypr/hyprland.conf",
        "sway": "~/.config/sway/config",
        "niri": "~/.config/niri/config.kdl (dentro de binds { })",
    }[desktop]
    return path, lines


def _summary(bindings: dict[str, list[str]]) -> list[str]:
    lines = []
    for action in actions.ACTIONS:
        keys = bindings.get(action.id, [])
        if keys:
            lines.append(f"  {' o '.join(label(k) for k in keys)} → {action.name}")
    return lines or ["  (ninguna acción tiene atajo)"]


def apply(bindings: dict[str, list[str]], old: dict[str, list[str]] | None = None) -> list[str]:
    """Pone estos atajos en el escritorio (y quita los anteriores). Devuelve mensajes."""
    desktop = config.desktop()
    old = old or {}
    summary = _summary(bindings)
    func = SETUP.get(desktop)
    if func is not None:
        try:
            notes = [f"Atajos configurados para {desktop}:", *summary, *func(bindings, old)]
        except ShortcutError as exc:
            notes = [str(exc), *summary]
    elif (manual := _manual_lines(desktop, bindings)) is not None:
        path, lines = manual
        notes = [f"Añade estas líneas a {path} (y quita las anteriores):", *lines]
    else:
        notes = [f"Escritorio «{desktop}» no reconocido. Asigna los atajos a mano:", *summary]
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.SHORTCUTS_MARKER.write_text(desktop + "\n", encoding="utf-8")
    return notes


def setup_shortcuts(force: bool = False) -> list[str]:
    """Configura los atajos guardados (o los predeterminados) la primera vez, o siempre con force."""
    if config.SHORTCUTS_MARKER.exists() and not force:
        return []
    return apply(actions.current(config.Settings()))
