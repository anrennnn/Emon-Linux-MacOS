"""Escribe el emoji elegido en la aplicación que tenía el foco.

Windows lo hace con su sistema de entrada de texto. En Linux depende de la sesión:

* X11 (cualquier escritorio): xdotool devuelve el foco a la ventana anterior y
  escribe el emoji como si se tecleara. El portapapeles no se toca.
* Wayland con Hyprland, Sway, niri, Wayfire o river: wtype lo escribe por el
  protocolo de teclado virtual.
* Wayland con GNOME o KDE Plasma: no dejan que un programa teclee en otro. El
  emoji se copia al portapapeles y, si ydotool está activo, se pulsa Ctrl+V;
  si no, se avisa para pegarlo a mano.
* macOS: se vuelve a la app anterior y se teclea con Quartz (necesita el permiso
  de Accesibilidad); sin permiso, queda copiado para pegarlo con ⌘V.
"""

import os
import shutil
import subprocess

from PyQt6.QtGui import QGuiApplication

from . import config

WLROOTS = ("hyprland", "sway", "niri", "wayfire", "river", "labwc")


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
    """'xdotool', 'wtype', 'quartz' o 'portapapeles'."""
    if config.IS_MACOS:
        from . import macos

        return "quartz" if macos.accessibility_allowed() else "portapapeles"
    if config.session_type() == "x11":
        return "xdotool" if shutil.which("xdotool") else "portapapeles"
    if config.desktop() in WLROOTS and shutil.which("wtype"):
        return "wtype"
    return "portapapeles"


def copy_now(text: str):
    """Hay que llamarlo con el panel aún visible: en Wayland solo copia quien tiene el foco."""
    QGuiApplication.clipboard().setText(text)


def insert(text: str, target: Target) -> str:
    """Escribe el texto. Devuelve '' si se escribió o un aviso para el usuario."""
    how = method()
    if config.IS_MACOS:
        return _insert_macos(text, target, how)
    if how == "xdotool":
        if target.window:
            _run("xdotool", "windowactivate", "--sync", target.window)
        result = _run("xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text)
        if result is not None and result.returncode == 0:
            return ""
    elif how == "wtype":
        result = _run("wtype", "--", text)
        if result is not None and result.returncode == 0:
            return ""

    if how != "portapapeles":
        # xdotool o wtype fallaron y el texto aún no se copió (copy_now solo se usa sin ellos).
        if config.session_type() == "x11":
            copy_now(text)
        elif shutil.which("wl-copy"):
            subprocess.Popen(["wl-copy", "--", text])

    # Queda en el portapapeles. Con ydotool se puede pegar solo.
    if config.session_type() == "wayland" and _ydotool_ready():
        # Códigos de evdev: 29 = Ctrl izquierdo, 47 = V.
        result = _run("ydotool", "key", "29:1", "47:1", "47:0", "29:0")
        if result is not None and result.returncode == 0:
            return ""
    return "Copiado al portapapeles: pulsa Ctrl+V para pegarlo."


def _insert_macos(text: str, target: Target, how: str) -> str:
    from . import macos

    macos.activate(target.app)
    if how == "quartz":
        if macos.fits_one_event(text):
            macos.type_text(text)
        else:
            copy_now(text)
            macos.paste()
        return ""
    return "Copiado: pulsa ⌘V para pegarlo. Para que se escriba solo, da permiso de Accesibilidad a Emojis."


def _ydotool_ready() -> bool:
    if not shutil.which("ydotool"):
        return False
    socket = os.environ.get("YDOTOOL_SOCKET") or f"/run/user/{os.getuid()}/.ydotool_socket"
    return os.path.exists(socket) or os.path.exists("/tmp/.ydotool_socket")
