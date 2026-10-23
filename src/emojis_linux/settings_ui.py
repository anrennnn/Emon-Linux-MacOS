"""Ventana para elegir el atajo que abre el panel."""

from . import config
from .qt import (
    QDialog, QHBoxLayout, QKeySequence, QKeySequenceEdit, QLabel, QLineEdit, QPushButton, Qt, QTimer, QVBoxLayout,
)
from .shortcuts import DEFAULT_KEYS, label, split

PORTABLE = QKeySequence.SequenceFormat.PortableText
_MODIFIERS = {"Meta", "Ctrl", "Alt", "Shift"}


class SingleKeyEdit(QKeySequenceEdit):
    """Graba una sola combinación y termina en cuanto se suelta la tecla principal.

    Sin esto, Qt < 6.5 espera un segundo por si llega otra combinación, y un Enter
    pulsado para guardar acabaría grabado como segunda tecla.
    """

    MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
                     Qt.Key.Key_Super_L, Qt.Key.Key_Super_R, Qt.Key.Key_AltGr}

    def __init__(self, after_finish):
        super().__init__()
        self.after_finish = after_finish
        if hasattr(self, "setMaximumSequenceLength"):  # Qt 6.5 o más reciente
            self.setMaximumSequenceLength(1)

    def clear(self):
        super().clear()
        # Qt vuelve a poner su texto de ejemplo («Press shortcut») al vaciarse, en inglés
        # si no tiene traducciones instaladas.
        field = self.findChild(QLineEdit)
        if field is not None:
            field.setPlaceholderText("Pulsa la combinación…")

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() not in self.MODIFIER_KEYS:
            # Al perder el foco, QKeySequenceEdit termina de grabar y avisa del cambio.
            QTimer.singleShot(0, self.after_finish)


def validate(key: str) -> str:
    """'' si el atajo vale; si no, el motivo."""
    if not key:
        return "Pulsa una combinación de teclas."
    mods, name = split(key)
    if name.startswith("F") and name[1:].isdigit():
        return ""  # F1…F12 valen solas
    if not set(mods) - {"Shift"}:
        modifiers = "⌘, ⌃ u ⌥" if config.IS_MACOS else "Super, Ctrl o Alt"
        return f"Añade {modifiers}: una tecla sola chocaría con lo que escribes."
    if any(m not in _MODIFIERS for m in mods):
        return "Esa tecla modificadora no se puede usar."
    return ""


class ShortcutDialog(QDialog):
    def __init__(self, settings: config.Settings, apply_keys, notify):
        """apply_keys(nuevos, anteriores) → mensajes para el usuario.

        settings es el mismo objeto que usa el panel: si fuera otro, al guardar los
        recientes el panel borraría el atajo elegido.
        """
        super().__init__()
        self.settings = settings
        self.apply_keys = apply_keys
        self.notify = notify
        self.setWindowTitle(f"{config.APP_NAME} - Atajo de teclado")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        title = QLabel("Atajo para abrir el panel de emojis")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)
        self.current = QLabel()
        layout.addWidget(self.current)

        layout.addWidget(QLabel("Haz clic en el cuadro y pulsa la nueva combinación:"))
        self.edit = SingleKeyEdit(lambda: self.save.setFocus())
        self.edit.keySequenceChanged.connect(self._changed)
        layout.addWidget(self.edit)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(self.message.fontMetrics().lineSpacing() * 2 + 4)
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        reset = QPushButton("Restaurar predeterminado")
        reset.clicked.connect(self._reset)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save = QPushButton("Guardar")
        self.save.setDefault(True)
        self.save.clicked.connect(self._save)
        buttons.addWidget(self.save)
        layout.addLayout(buttons)

    def open_dialog(self):
        from .theme import Theme

        self.setPalette(Theme().palette())  # claro u oscuro como el escritorio
        keys = self.settings.shortcuts or list(DEFAULT_KEYS)
        self.current.setText("Ahora: " + " o ".join(label(k) for k in keys))
        self.edit.clear()
        self._show_message("")
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()

    def _key(self) -> str:
        sequence = self.edit.keySequence()
        return sequence.toString(PORTABLE).split(", ")[0] if not sequence.isEmpty() else ""

    def _changed(self, sequence):
        # Qt < 6.5 admite hasta cuatro combinaciones seguidas: nos quedamos con la primera.
        if sequence.count() > 1:
            self.edit.setKeySequence(QKeySequence(self._key()))
            return
        key = self._key()
        problem = validate(key)
        self._show_message(problem or f"Nuevo atajo: {label(key)}. Pulsa Guardar.", error=bool(problem))

    def _show_message(self, text: str, error: bool = False):
        self.message.setText(text)
        self.message.setStyleSheet("color: #c42b1c;" if error else "")

    def _apply(self, keys: list[str], stored: list[str]):
        old = self.settings.shortcuts or list(DEFAULT_KEYS)
        self.settings.set_shortcuts(stored)
        notes = self.apply_keys(keys, old)
        self.notify("\n".join(notes))
        self.accept()

    def _save(self):
        key = self._key()
        problem = validate(key)
        if problem:
            self._show_message(problem, error=True)
            return
        self._apply([key], [key])

    def _reset(self):
        self._apply(list(DEFAULT_KEYS), [])
