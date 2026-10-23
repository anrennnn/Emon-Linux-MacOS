"""Escribe el emoji elegido en la aplicación que tenía el foco.

Windows lo hace con su sistema de entrada de texto. En Linux depende de la sesión:

* X11 (cualquier escritorio): xdotool devuelve el foco a la ventana anterior y
  escribe el emoji como si se tecleara. El portapapeles no se toca.
* Wayland con Hyprland, Sway, niri, Wayfire o river: wtype lo escribe por el
  protocolo de teclado virtual.
* Wayland con GNOME o KDE Plasma: no dejan que un programa teclee en otro. El
  emoji se copia y se pulsa Ctrl+V con el portal RemoteDesktop (la primera vez
  el escritorio pide permiso; ver portal.py) o con ydotool si está activo. Si
  nada de eso está disponible, se avisa para pegarlo a mano.

Cuando se pega desde el portapapeles, después se deja en él lo que había antes,
como en Windows, donde el panel no lo toca.
* macOS: se vuelve a la app anterior y se teclea con Quartz (necesita el permiso
  de Accesibilidad); sin permiso, queda copiado para pegarlo con ⌘V.
"""

import os
import shutil
import subprocess

from . import config
from .qt import QGuiApplication

WLROOTS = ("hyprland", "sway", "niri", "wayfire", "river", "labwc")

_remote = None  # portal.RemoteKeyboard, lo crea configure()
_previous_clipboard = None  # texto que había antes de copiar el emoji


def configure(settings: config.Settings):
    """Prepara el portal RemoteDesktop, que guarda su permiso en los ajustes."""
    global _remote
    if config.session_type() == "wayland":
        from .portal import RemoteKeyboard

        _remote = RemoteKeyboard(lambda: settings.keyboard_token, settings.set_keyboard_token)


def _run(*cmd, timeout=3) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


class Target:
    """La ventana que tenía el foco antes de abrir el panel."""

    def __init__(self):
        self.window = ""
        self.app = None
        if config.IS_MACOS:
            from . import macos

            self.app = macos.frontmost_app()
            return
        if config.session_type() == "x11" and shutil.which("xdotool"):
            result = _run("xdotool", "getactivewindow")
            if result is not None and result.returncode == 0:
                self.window = result.stdout.strip()


def method() -> str:
    """'xdotool', 'wtype', 'quartz', 'ydotool', 'portal' o 'portapapeles'."""
    if config.IS_MACOS:
        from . import macos

        return "quartz" if macos.accessibility_allowed() else "portapapeles"
    if config.session_type() == "x11":
        return "xdotool" if shutil.which("xdotool") else "portapapeles"
    if config.desktop() in WLROOTS and shutil.which("wtype"):
        return "wtype"
    if _ydotool_ready():
        return "ydotool"
    if _remote is not None and _remote.available():
        return "portal"
    return "portapapeles"


def uses_clipboard(how: str) -> bool:
    return how in ("ydotool", "portal", "portapapeles")


def copy_now(text: str):
    """Hay que llamarlo con el panel aún visible: en Wayland solo copia quien tiene el foco."""
    global _previous_clipboard
    clipboard = QGuiApplication.clipboard()
    data = clipboard.mimeData()
    # Solo se recupera después si era texto: una imagen o archivos no se pueden guardar fácil.
    only_text = data is not None and data.hasText() and not data.hasImage() and not data.hasUrls()
    _previous_clipboard = clipboard.text() if only_text else None
    clipboard.setText(text)


def _restore_clipboard(text: str):
    """Pasado un momento (la app ya leyó el emoji), vuelve a dejar lo que había."""
    from .qt import QTimer

    previous = _previous_clipboard
    if previous is None or previous == text:
        return

    def restore():
        clipboard = QGuiApplication.clipboard()
        if clipboard.text() == text:  # si el usuario copió otra cosa entretanto, no se toca
            clipboard.setText(previous)

    QTimer.singleShot(1500, restore)


def insert(text: str, target: Target, report):
    """Escribe el texto. Si no se puede, llama a report(aviso para el usuario)."""
    how = method()
    if config.IS_MACOS:
        message = _insert_macos(text, target, how)
        if message:
            report(message)
        return
    if how == "xdotool":
        if target.window:
            _run("xdotool", "windowactivate", "--sync", target.window)
        result = _run("xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text)
        if result is not None and result.returncode == 0:
            return
        copy_now(text)  # en X11 se puede copiar aunque el panel ya no tenga el foco
    elif how == "wtype":
        result = _run("wtype", "--", text)
        if result is not None and result.returncode == 0:
            return
        if shutil.which("wl-copy"):
            subprocess.Popen(["wl-copy", "--", text])
    elif how == "ydotool":
        # Códigos de evdev: 29 = Ctrl izquierdo, 47 = V.
        result = _run("ydotool", "key", "29:1", "47:1", "47:0", "29:0")
        if result is not None and result.returncode == 0:
            _restore_clipboard(text)
            return
    elif how == "portal":
        def done(ok: bool):
            if ok:
                _restore_clipboard(text)
            else:
                report("Copiado al portapapeles: pulsa Ctrl+V para pegarlo. "
                       "Para que se pegue solo, acepta el permiso que pide el escritorio.")

        _remote.paste(done)
        return
    report("Copiado al portapapeles: pulsa Ctrl+V para pegarlo.")


def _insert_macos(text: str, target: Target, how: str) -> str:
    from . import macos

    macos.activate(target.app)
    if how == "quartz":
        if macos.fits_one_event(text):
            macos.type_text(text)
        else:
            copy_now(text)
            macos.paste()
            _restore_clipboard(text)
        return ""
    return "Copiado: pulsa ⌘V para pegarlo. Para que se escriba solo, da permiso de Accesibilidad a Emojis."


def _ydotool_ready() -> bool:
    if not shutil.which("ydotool"):
        return False
    socket = os.environ.get("YDOTOOL_SOCKET") or f"/run/user/{os.getuid()}/.ydotool_socket"
    return os.path.exists(socket) or os.path.exists("/tmp/.ydotool_socket")
