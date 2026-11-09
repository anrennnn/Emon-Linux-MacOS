"""Acciones que Emon puede abrir con un atajo de teclado.

Cada acción tiene un identificador (el mismo que su subcomando de `emon`), un
nombre para la ventana de atajos, el comando que se registra en el escritorio y
las combinaciones predeterminadas. El usuario puede cambiar estas últimas
acción por acción desde ⚙ o con `emon ajustes`.
"""

from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Action:
    id: str
    name: str
    command: str
    defaults: tuple[str, ...]


# En macOS, Qt llama «Ctrl» a ⌘ y «Meta» a ⌃: el predeterminado es ⌃⌘. (⌘. es «cancelar»).
_EMOJI = "Meta+Ctrl+." if config.IS_MACOS else "Meta+."
_SYMBOLS = "Meta+Ctrl+;" if config.IS_MACOS else "Meta+;"
# Hasta la 0.3 los dos atajos (los predeterminados) abrían el panel.
_LEGACY_KEYS = (_EMOJI, _SYMBOLS)

ACTIONS: tuple[Action, ...] = (
    Action("abrir", "Abrir el panel de emojis", "emon abrir", (_EMOJI,)),
    Action("simbolos", "Abrir la pestaña de símbolos", "emon simbolos", (_SYMBOLS,)),
    Action("ajustes", "Abrir los ajustes de atajos", "emon ajustes", ()),
)
ACTIONS_BY_ID = {action.id: action for action in ACTIONS}


def defaults() -> dict[str, list[str]]:
    """Los atajos de fábrica de cada acción."""
    return {action.id: list(action.defaults) for action in ACTIONS}


def _normalized(key: str) -> tuple[str, ...]:
    """La combinación sin depender del orden de los modificadores (sin Qt)."""
    if key.endswith("++"):
        mods, name = [m for m in key[:-2].split("+") if m], "+"
    else:
        *mods, name = key.split("+")
    return tuple(sorted(m for m in mods if m)) + (name,)


def current(settings: config.Settings) -> dict[str, list[str]]:
    """Los atajos guardados, completados con los predeterminados que falten.

    Una acción con una lista vacía guardada se queda sin atajo: el usuario pudo
    borrarlo a propósito. Si dos acciones acaban con la misma combinación (por
    ejemplo al migrar los atajos antiguos), se queda la primera.
    """
    stored = settings.bindings
    result: dict[str, list[str]] = {}
    used: set[tuple[str, ...]] = set()
    for action in ACTIONS:
        if action.id in stored:
            keys = list(stored[action.id])
            if action.id == "abrir" and settings.legacy_shortcuts and keys == list(_LEGACY_KEYS):
                # «Restaurar predeterminado» de la versión anterior guardaba los dos
                # atajos para abrir el panel: ahora el segundo es el de símbolos.
                keys = list(action.defaults)
        else:
            keys = list(action.defaults)
        clean = []
        for key in keys:
            written = _normalized(key)
            if written not in used:
                used.add(written)
                clean.append(key)
        result[action.id] = clean
    return result
