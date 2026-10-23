"""Lo propio de macOS: atajo global, volver a la app anterior y escribir el emoji.

* El atajo (por defecto ⌃⌘. y ⌃⌘;, se puede cambiar en los ajustes) se registra
  con RegisterEventHotKey de Carbon, que no necesita permisos especiales. ⌘. no
  se usa porque en macOS es «cancelar».
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

# Códigos de tecla virtuales de un teclado ANSI (Events.h de Carbon).
_KVK = {
    "A": 0x00, "S": 0x01, "D": 0x02, "F": 0x03, "H": 0x04, "G": 0x05, "Z": 0x06, "X": 0x07, "C": 0x08,
    "V": 0x09, "B": 0x0B, "Q": 0x0C, "W": 0x0D, "E": 0x0E, "R": 0x0F, "Y": 0x10, "T": 0x11, "1": 0x12,
    "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17, "=": 0x18, "9": 0x19, "7": 0x1A, "-": 0x1B,
    "8": 0x1C, "0": 0x1D, "]": 0x1E, "O": 0x1F, "U": 0x20, "[": 0x21, "I": 0x22, "P": 0x23, "L": 0x25,
    "J": 0x26, "'": 0x27, "K": 0x28, ";": 0x29, "\\": 0x2A, ",": 0x2B, "/": 0x2C, "N": 0x2D, "M": 0x2E,
    ".": 0x2F, "`": 0x32, "Space": 0x31, "Return": 0x24, "Tab": 0x30,
    "F1": 0x7A, "F2": 0x78, "F3": 0x63, "F4": 0x76, "F5": 0x60, "F6": 0x61, "F7": 0x62, "F8": 0x64,
    "F9": 0x65, "F10": 0x6D, "F11": 0x67, "F12": 0x69,
}
_KVK_V = 0x09
# Qt en macOS: «Ctrl» es ⌘ y «Meta» es ⌃.
_CARBON_MODS = {"Ctrl": 0x0100, "Shift": 0x0200, "Alt": 0x0800, "Meta": 0x1000}


def carbon_key(key: str) -> tuple[int, int] | None:
    """«Meta+Ctrl+.» → (código de tecla, modificadores de Carbon), o None si no se puede."""
    from .shortcuts import split

    mods, name = split(key)
    code = _KVK.get(name.upper() if len(name) == 1 else name)
    if code is None or any(m not in _CARBON_MODS for m in mods):
        return None
    flags = 0
    for m in mods:
        flags |= _CARBON_MODS[m]
    return code, flags

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

    def __init__(self, on_press, keys: list[str]):
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
        carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        carbon.GetEventParameter.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p,
        ]
        self.carbon = carbon
        # Hay que guardar la función: si Python la libera, macOS llamaría a memoria inválida.
        self.handler = _HANDLER(self._handle)
        spec = _EventTypeSpec(_fourcc("keyb"), 5)  # kEventClassKeyboard, kEventHotKeyPressed
        self.target = carbon.GetApplicationEventTarget()
        carbon.InstallEventHandler(self.target, self.handler, 1, ctypes.byref(spec), None, None)
        self.set_keys(keys)

    def set_keys(self, keys: list[str]) -> list[str]:
        """Cambia los atajos. Devuelve los que no se pudieron registrar."""
        for ref in self.refs:
            self.carbon.UnregisterEventHotKey(ref)
        self.refs = []
        failed = []
        for n, key in enumerate(keys, start=1):
            parsed = carbon_key(key)
            ref = ctypes.c_void_p()
            status = -1
            if parsed is not None:
                code, mods = parsed
                status = self.carbon.RegisterEventHotKey(
                    code, mods, _EventHotKeyID(_fourcc("EMOJ"), n), self.target, 0, ctypes.byref(ref)
                )
            if status == 0:
                self.refs.append(ref)
            else:
                print(f"No se pudo registrar el atajo {key} (código {status}): ¿lo usa otra app?", file=sys.stderr)
                failed.append(key)
        return failed

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
    from .shortcuts import current_keys, label

    notes = [f"Pulsa {label(current_keys()[0])} en cualquier app para abrir los emojis."]
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
