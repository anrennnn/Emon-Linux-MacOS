"""Ventana para elegir los atajos de cada acción de Emon."""

from . import actions, config
from .qt import (
    QDialog, QHBoxLayout, QKeySequence, QKeySequenceEdit, QLabel, QLineEdit, QPushButton, Qt, QTimer, QToolButton,
    QVBoxLayout, QWidget,
)
from .shortcuts import label, split

PORTABLE = QKeySequence.SequenceFormat.PortableText
_MODIFIERS = {"Meta", "Ctrl", "Alt", "Shift"}


def canonical(key: str) -> str:
    """La misma combinación escrita siempre igual, para comparar sin falsos negativos."""
    return QKeySequence(key).toString(PORTABLE)


class SingleKeyEdit(QKeySequenceEdit):
    """Graba una sola combinación y termina en cuanto se suelta la tecla principal.

    Sin esto, Qt < 6.5 espera un segundo por si llega otra combinación, y un Enter
    pulsado para guardar acabaría grabado como segunda tecla.
    """

    MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
                     Qt.Key.Key_Super_L, Qt.Key.Key_Super_R, Qt.Key.Key_AltGr}

    def __init__(self, after_finish=lambda: None):
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


def _sequence(edit: QKeySequenceEdit) -> str:
    sequence = edit.keySequence()
    return sequence.toString(PORTABLE).split(", ")[0] if not sequence.isEmpty() else ""


class CaptureDialog(QDialog):
    """Pide una combinación nueva. Aceptar solo se activa si es válida."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Nueva combinación")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Haz clic en el cuadro y pulsa la combinación:"))
        self.edit = SingleKeyEdit(lambda: self.ok.setFocus())
        self.edit.clear()
        self.edit.keySequenceChanged.connect(self._changed)
        layout.addWidget(self.edit)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(self.message.fontMetrics().lineSpacing() + 4)
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.ok = QPushButton("Aceptar")
        self.ok.setDefault(True)
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self.accept)
        buttons.addWidget(self.ok)
        layout.addLayout(buttons)

    def _changed(self, sequence):
        # Qt < 6.5 admite hasta cuatro combinaciones seguidas: nos quedamos con la primera.
        if sequence.count() > 1:
            self.edit.setKeySequence(QKeySequence(_sequence(self.edit)))
            return
        problem = validate(_sequence(self.edit))
        self.message.setText(problem)
        self.message.setStyleSheet("color: #c42b1c;" if problem else "")
        self.ok.setEnabled(not problem)

    def key(self) -> str:
        return _sequence(self.edit)

    def accept(self):
        if validate(self.key()):
            return
        super().accept()


class ShortcutDialog(QDialog):
    def __init__(self, settings: config.Settings, apply_keys, notify):
        """apply_keys(atajos nuevos, anteriores) → mensajes para el usuario.

        settings es el mismo objeto que usa el panel: si fuera otro, al guardar los
        recientes el panel borraría los atajos elegidos.
        """
        super().__init__()
        self.settings = settings
        self.apply_keys = apply_keys
        self.notify = notify
        self.keys = actions.defaults()
        self.setWindowTitle(f"{config.APP_NAME} - Atajos de teclado")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        title = QLabel("Atajos de teclado")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Cada acción puede tener su propia combinación. Pulsa una para cambiarla."))

        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        layout.addLayout(self.body)

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
        self.keys = actions.current(self.settings)
        self._render()
        self._show_message("")
        self.show()
        self.raise_()
        self.activateWindow()

    def _render(self):
        while self.body.count():
            item = self.body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for action in actions.ACTIONS:
            self.body.addWidget(self._row(action))

    def _row(self, action: actions.Action) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        name = QLabel(action.name)
        name.setMinimumWidth(210)
        layout.addWidget(name)

        keys = self.keys.get(action.id, [])
        if not keys:
            empty = QLabel("Sin atajo")
            empty.setEnabled(False)
            layout.addWidget(empty)
        for index, key in enumerate(keys):
            chip = QPushButton(label(key))
            chip.setToolTip("Cambiar esta combinación")
            chip.clicked.connect(lambda _, a=action.id, i=index: self._capture(a, i))
            layout.addWidget(chip)
            remove = QToolButton()
            remove.setText("✕")
            remove.setToolTip("Quitar esta combinación")
            remove.clicked.connect(lambda _, a=action.id, i=index: self._remove(a, i))
            layout.addWidget(remove)

        add = QPushButton("Añadir")
        add.setToolTip("Añadir otra combinación para esta acción")
        add.clicked.connect(lambda _, a=action.id: self._capture(a, None))
        layout.addWidget(add)
        layout.addStretch(1)
        return row

    def _remove(self, action_id: str, index: int):
        del self.keys[action_id][index]
        self._render()

    def _capture(self, action_id: str, index: int | None):
        dialog = CaptureDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        key = dialog.key()
        problem = validate(key)
        if problem:
            self._show_message(problem, error=True)
            return
        other = self._conflict(action_id, index, key)
        if other is not None:
            self._show_message(f"{label(key)} ya abre «{other}». Elige otra combinación.", error=True)
            return
        if index is None:
            self.keys[action_id].append(key)
        else:
            self.keys[action_id][index] = key
        self._render()
        self._show_message(f"Nuevo atajo: {label(key)}. Pulsa Guardar.")

    def _conflict(self, action_id: str, index: int | None, key: str) -> str | None:
        target = canonical(key)
        for action in actions.ACTIONS:
            for position, other in enumerate(self.keys.get(action.id, [])):
                if action.id == action_id and position == index:
                    continue
                if canonical(other) == target:
                    return action.name
        return None

    def _show_message(self, text: str, error: bool = False):
        self.message.setText(text)
        self.message.setStyleSheet("color: #c42b1c;" if error else "")

    def _reset(self):
        self.keys = actions.defaults()
        self._render()
        self._show_message("Atajos predeterminados. Pulsa Guardar para aplicarlos.")

    def _save(self):
        if not self.keys.get("abrir"):
            self._show_message("Deja al menos un atajo para abrir el panel.", error=True)
            return
        for action in actions.ACTIONS:
            for key in self.keys.get(action.id, []):
                problem = validate(key)
                if problem:
                    self._show_message(f"{action.name}: {problem}", error=True)
                    return
        seen: dict[str, str] = {}
        for action in actions.ACTIONS:
            for key in self.keys.get(action.id, []):
                written = canonical(key)
                if written in seen:
                    self._show_message(
                        f"{label(key)} está en «{action.name}» y en «{seen[written]}».", error=True
                    )
                    return
                seen[written] = action.name

        old = actions.current(self.settings)
        self.settings.set_bindings(self.keys)
        notes = self.apply_keys(dict(self.keys), old)
        self.notify("\n".join(notes))
        self.accept()
