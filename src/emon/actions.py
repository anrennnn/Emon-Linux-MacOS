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

ACTIONS: tuple[Action, ...] = (
    Action("abrir", "Abrir el panel de emojis", "emon abrir", (_EMOJI,)),
    Action("simbolos", "Abrir la pestaña de símbolos", "emon simbolos", (_SYMBOLS,)),
    Action("ajustes", "Abrir los ajustes de atajos", "emon ajustes", ()),
)
ACTIONS_BY_ID = {action.id: action for action in ACTIONS}


def defaults() -> dict[str, list[str]]:
    """Los atajos de fábrica de cada acción."""
    return {action.id: list(action.defaults) for action in ACTIONS}


def current(settings: config.Settings) -> dict[str, list[str]]:
    """Los atajos guardados, completados con los predeterminados que falten.

    Una acción con una lista vacía guardada se queda sin atajo: el usuario pudo
    borrarlo a propósito.
    """
    stored = settings.bindings
    return {
        action.id: list(stored[action.id]) if action.id in stored else list(action.defaults)
        for action in ACTIONS
    }
