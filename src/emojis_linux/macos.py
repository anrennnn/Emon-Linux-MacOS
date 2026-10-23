"""Lo propio de macOS: atajo global, volver a la app anterior y escribir el emoji.

* El atajo (⌃⌘. y ⌃⌘;) se registra con RegisterEventHotKey de Carbon, que no
  necesita permisos especiales. ⌘. no se usa porque en macOS es «cancelar».
* Para escribir en otra app se envían pulsaciones con CGEventPost (Quartz).
  macOS solo lo permite si el usuario da permiso de Accesibilidad a Emojis;
  sin él, el emoji queda copiado y se avisa para pegarlo con ⌘V.
"""

import ctypes
import plistlib
import subprocess
import sys
from pathlib import Path

from . import config

HOTKEY_LABEL = "⌃⌘."

# Códigos de tecla virtuales (Events.h) y modificadores de Carbon.
_KVK_PERIOD, _KVK_SEMICOLON, _KVK_V = 0x2F, 0x29, 0x09
_CMD_KEY, _CONTROL_KEY = 0x0100, 0x1000

# CGEventKeyboardSetUnicodeString admite como mucho 20 unidades UTF-16 por evento.
_MAX_UTF16 = 20


def _fourcc(code: str) -> int:
    return int.from_bytes(code.encode("ascii"), "big")


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


class HotKeys:
    """Atajos globales. on_press se llama en el hilo principal (bucle de eventos de Qt)."""

    def __init__(self, on_press):
        self.on_press = on_press
        self.refs = []
        carbon = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
        carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
        carbon.InstallEventHandler.argtypes = [
            ctypes.c_void_p, _HANDLER, ctypes.c_uint32, ctypes.POINTER(_EventTypeSpec),
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ]
        carbon.RegisterEventHotKey.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
        ]
        carbon.GetEventParameter.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p,
        ]
        self.carbon = carbon
        # Hay que guardar la función: si Python la libera, macOS llamaría a memoria inválida.
        self.handler = _HANDLER(self._handle)
        spec = _EventTypeSpec(_fourcc("keyb"), 5)  # kEventClassKeyboard, kEventHotKeyPressed
        target = carbon.GetApplicationEventTarget()
        carbon.InstallEventHandler(target, self.handler, 1, ctypes.byref(spec), None, None)
        for n, key in enumerate((_KVK_PERIOD, _KVK_SEMICOLON), start=1):
            ref = ctypes.c_void_p()
            status = carbon.RegisterEventHotKey(
                key, _CMD_KEY | _CONTROL_KEY, _EventHotKeyID(_fourcc("EMOJ"), n), target, 0, ctypes.byref(ref)
            )
            if status == 0:
                self.refs.append(ref)
            else:
                print(f"No se pudo registrar el atajo (código {status}): ¿lo usa otra app?", file=sys.stderr)

    def _handle(self, _call_ref, _event, _data):
        try:
            self.on_press()
        except Exception as exc:  # una excepción aquí cerraría la app
            print("Error en el atajo:", exc, file=sys.stderr)
        return 0


# --- aplicaciones ------------------------------------------------------------


def become_accessory():
    """Sin icono en el Dock ni menú propio, como un panel del sistema."""
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)


def activate_self():
    from AppKit import NSApplication

    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)


def frontmost_app():
    from AppKit import NSRunningApplication, NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None or app.processIdentifier() == NSRunningApplication.currentApplication().processIdentifier():
        return None
    return app


def activate(app):
    """Vuelve a poner delante la app anterior y espera a que lo esté."""
    if app is None:
        return
    import time

    app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
    for _ in range(20):
        if app.isActive():
            break
        time.sleep(0.025)


# --- escribir ----------------------------------------------------------------


def accessibility_allowed() -> bool:
    try:
        lib = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except OSError:
        return False


def open_accessibility_settings():
    subprocess.Popen(
        ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"]
    )


def type_text(text: str):
    """Escribe el texto en la app activa como si se tecleara."""
    from Quartz import (
        CGEventCreateKeyboardEvent, CGEventKeyboardSetUnicodeString, CGEventPost, CGEventSetFlags, kCGHIDEventTap,
    )

    for down in (True, False):
        event = CGEventCreateKeyboardEvent(None, 0, down)
        CGEventSetFlags(event, 0)  # sin ⌘ ni ⌃ pegados del atajo
        CGEventKeyboardSetUnicodeString(event, len(text.encode("utf-16-le")) // 2, text)
        CGEventPost(kCGHIDEventTap, event)


def paste():
    """⌘V en la app activa."""
    from Quartz import CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags, kCGEventFlagMaskCommand, kCGHIDEventTap

    for down in (True, False):
        event = CGEventCreateKeyboardEvent(None, _KVK_V, down)
        CGEventSetFlags(event, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event)


def fits_one_event(text: str) -> bool:
    # Banderas como 🏴󠁧󠁢󠁳󠁣󠁴󠁿 pasan de 20 unidades: esas se pegan desde el portapapeles.
    return len(text.encode("utf-16-le")) // 2 <= _MAX_UTF16


# --- otros -------------------------------------------------------------------


def notify(title: str, body: str):
    script = f"display notification {_applescript(body)} with title {_applescript(title)}"
    subprocess.Popen(["osascript", "-e", script])


def _applescript(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def system_locale() -> str:
    """Idioma de macOS (las apps abiertas desde el Finder no tienen LANG)."""
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleLocale"], capture_output=True, text=True, timeout=2
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    return out.split("@")[0]


LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / "io.github.anrennnn.emojis.plist"


def setup_login_item() -> list[str]:
    """La primera vez: arrancar Emojis al iniciar sesión y explicar el atajo."""
    if config.SHORTCUTS_MARKER.exists():
        return []
    notes = [f"Pulsa {HOTKEY_LABEL} en cualquier app para abrir los emojis."]
    if getattr(sys, "frozen", False):
        # Dentro de Emojis.app (PyInstaller): sys.executable es el ejecutable de la app.
        LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
        LAUNCH_AGENT.write_bytes(plistlib.dumps({
            "Label": "io.github.anrennnn.emojis",
            "ProgramArguments": [sys.executable, "segundo-plano"],
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }))
        notes.append("Emojis se abrirá solo al iniciar sesión.")
    if not accessibility_allowed():
        notes.append("Para que el emoji se escriba solo, permite Emojis en Ajustes → Privacidad → Accesibilidad.")
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.SHORTCUTS_MARKER.write_text("macos\n", encoding="utf-8")
    return notes


def remove_login_item():
    LAUNCH_AGENT.unlink(missing_ok=True)
