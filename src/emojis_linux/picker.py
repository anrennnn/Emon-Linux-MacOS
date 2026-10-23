"""Panel de emojis y símbolos (Super+.), al estilo de Windows 11."""

from . import config, inserter
from .catalog import EMOJI_FONTS, Catalog, Item, Section, search
from .qt import (
    QAbstractItemView, QAbstractListModel, QButtonGroup, QColor, QCursor, QFont, QFrame, QGuiApplication,
    QHBoxLayout, QLabel, QLineEdit, QListView, QMenu, QModelIndex, QPainter, QPainterPath, QPoint, QRectF,
    QRegion, QSize, QStyle, QStyledItemDelegate, Qt, QTextLayout, QTimer, QToolButton, QVBoxLayout, QWidget,
    font_families, pyqtSignal,
)

WIDTH, HEIGHT = 384, 470
TONE_SAMPLE = "✋"
TONE_NAMES = ["Predeterminado", "Claro", "Claro medio", "Medio", "Oscuro medio", "Oscuro"]
RECENT = "recientes"
INVISIBLE = ("\ufe0f", "\ufe0e", "\u200d")


def emoji_font() -> QFont:
    families = set(font_families())
    for name in EMOJI_FONTS:
        if name in families:
            return QFont(name)
    return QFont()


def shown(text: str) -> str:
    """Lo que se dibuja. Qt pinta U+FE0F con otra fuente y eso rompe secuencias como ❤️‍🔥;
    sin él la fuente de emojis las une igual. Lo que se escribe sí lleva U+FE0F."""
    return text.replace("\ufe0f", "") if len(text) > 1 else text


def support_checker(font: QFont):
    """Devuelve una función que dice si la fuente dibuja el emoji como un único dibujo.

    Si falta un emoji (por ejemplo, uno de Emoji 18.0 con una fuente antigua),
    se ve como una caja vacía o como varios emojis sueltos; así se detecta.
    """
    font = QFont(font)
    font.setPixelSize(24)
    family = font.family()

    def supported(text: str) -> bool:
        text = shown(text)
        layout = QTextLayout(text, font)
        layout.beginLayout()
        layout.createLine()
        layout.endLayout()
        own, other = [], 0
        for run in layout.glyphRuns():
            if run.rawFont().familyName() == family:
                own += run.glyphIndexes()
            else:
                other += len(run.glyphIndexes())
        # Qt dibuja aparte los caracteres invisibles (U+FE0F, U+200D) con otra fuente;
        # cualquier otro dibujo ajeno significa que la fuente de emojis no lo tiene.
        return len(own) == 1 and own[0] != 0 and other <= sum(text.count(c) for c in INVISIBLE)

    return supported


def _is_dark() -> bool:
    return QGuiApplication.palette().window().color().lightness() < 128


def _colors() -> dict:
    if _is_dark():
        return dict(bg="#202020", field="#2d2d2d", hover="#383838", text="#ffffff", sub="#c5c5c5",
                    border="#3b3b3b", accent="#4cc2ff")
    return dict(bg="#f3f3f3", field="#ffffff", hover="#e6e6e6", text="#1b1b1b", sub="#5f5f5f",
                border="#dcdcdc", accent="#005fb8")


def _stylesheet() -> str:
    c = _colors()
    return f"""
        #panel {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 10px; }}
        QLabel {{ color: {c['text']}; }}
        #section {{ color: {c['sub']}; font-weight: 600; padding: 2px 4px; }}
        #empty {{ color: {c['sub']}; }}
        QLineEdit {{ background: {c['field']}; color: {c['text']}; border: 1px solid {c['border']};
                     border-bottom: 2px solid {c['accent']}; border-radius: 5px; padding: 6px 8px; }}
        QListView {{ background: transparent; border: none; outline: none; }}
        QToolButton {{ color: {c['text']}; background: transparent; border: none; border-radius: 5px;
                       padding: 3px 6px; }}
        QToolButton:hover {{ background: {c['hover']}; }}
        QToolButton:checked {{ background: {c['hover']}; border-bottom: 2px solid {c['accent']}; }}
        #tab {{ font-size: 14px; padding: 5px 10px; }}
        #categoria {{ padding: 0px; }}
        QMenu {{ background: {c['field']}; color: {c['text']}; border: 1px solid {c['border']}; }}
        QMenu::item {{ padding: 4px 14px; }}
        QMenu::item:selected {{ background: {c['hover']}; }}
    """


class GridModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.cells: list[tuple[str, str]] = []  # (texto que se escribe, nombre)

    def set_cells(self, cells):
        self.beginResetModel()
        self.cells = cells
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.cells)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        text, name = self.cells[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return shown(text)
        if role == Qt.ItemDataRole.UserRole:
            return text
        if role == Qt.ItemDataRole.ToolTipRole:
            return name or None
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return name or text
        return None


class CellDelegate(QStyledItemDelegate):
    def __init__(self, view: QListView):
        super().__init__(view)
        self.view = view

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(2, 2, -2, -2)
        c = _colors()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QColor(c["accent"]))
            painter.setBrush(QColor(c["hover"]))
            painter.drawRoundedRect(rect, 6, 6)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c["hover"]))
            painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor(c["text"]))
        painter.setFont(self.view.font())
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, index.data())
        painter.restore()

    def sizeHint(self, option, index):
        return self.view.gridSize()


class Grid(QListView):
    activated_text = pyqtSignal(str)
    context_requested = pyqtSignal(int)
    typed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setWrapping(True)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setItemDelegate(CellDelegate(self))
        self.model_ = GridModel()
        self.setModel(self.model_)
        self.clicked.connect(lambda idx: self.activated_text.emit(idx.data(Qt.ItemDataRole.UserRole)))

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.currentIndex().isValid():
            self.activated_text.emit(self.currentIndex().data(Qt.ItemDataRole.UserRole))
            return
        if event.text() and event.text().isprintable() and key not in (Qt.Key.Key_Space,):
            self.typed.emit(event.text())  # escribir desde la cuadrícula va a la búsqueda
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        idx = self.indexAt(event.pos())
        if idx.isValid():
            self.setCurrentIndex(idx)
            self.context_requested.emit(idx.row())


class SearchBox(QLineEdit):
    move_down = pyqtSignal()
    accept_first = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Tab):
            self.move_down.emit()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept_first.emit()
            return
        super().keyPressEvent(event)


class EmojiPanel(QWidget):
    def __init__(self, catalog: Catalog, settings: config.Settings, notify):
        super().__init__()
        self.catalog = catalog
        self.settings = settings
        self.notify = notify
        self.tab = "emojis"
        self.section_key = RECENT
        self.cells_items: list[Item | None] = []
        self.target = inserter.Target()
        self.menu_open = False
        self.open_settings = lambda: None  # lo pone el proceso de fondo

        self.setWindowTitle(f"{config.APP_NAME} - Panel de emojis")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.use_mask = QGuiApplication.platformName() == "xcb"
        if not self.use_mask:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WIDTH, HEIGHT)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame(self)
        frame.setObjectName("panel")
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Pestañas superiores: Emojis | Símbolos
        header = QHBoxLayout()
        self.tab_group = QButtonGroup(self)
        self.tab_buttons = {}
        for key, label, tip in (("emojis", "😊", "Emojis"), ("simbolos", "Ω", "Símbolos")):
            btn = QToolButton(frame)
            btn.setObjectName("tab")
            btn.setText(label)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            if key == "emojis":
                btn.setFont(self._font_for("emojis", 16))
            btn.clicked.connect(lambda _, k=key: self.show_tab(k))
            self.tab_group.addButton(btn)
            self.tab_buttons[key] = btn
            header.addWidget(btn)
        header.addStretch(1)
        gear = QToolButton(frame)
        gear.setText("⚙")
        gear.setToolTip("Cambiar el atajo de teclado")
        gear.clicked.connect(lambda: self.open_settings())
        header.addWidget(gear)
        close = QToolButton(frame)
        close.setText("✕")
        close.setToolTip("Cerrar (Esc)")
        close.clicked.connect(self.hide)
        header.addWidget(close)
        layout.addLayout(header)

        self.search = SearchBox(frame)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.search.move_down.connect(self._focus_grid)
        self.search.accept_first.connect(self._accept_first)
        layout.addWidget(self.search)

        self.section_label = QLabel(frame)
        self.section_label.setObjectName("section")
        layout.addWidget(self.section_label)

        self.grid = Grid(frame)
        self.grid.activated_text.connect(self.choose)
        self.grid.context_requested.connect(self._tone_menu_for)
        self.grid.typed.connect(self._type_into_search)
        layout.addWidget(self.grid, 1)

        self.empty = QLabel("No se encontró nada", frame)
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty, 1)

        # Barra inferior: categorías y tono de piel
        self.footer = QHBoxLayout()
        self.footer.setSpacing(0)
        layout.addLayout(self.footer)
        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(False)  # refresh() marca la categoría (o ninguna al buscar)

        self.tone_button = QToolButton(frame)
        self.tone_button.setToolTip("Tono de piel")
        self.tone_button.setFont(self._font_for("emojis", 15))
        self.tone_button.setObjectName("categoria")
        self.tone_button.setFixedSize(32, 32)
        self.tone_button.clicked.connect(self._choose_tone)

        self.setStyleSheet(_stylesheet())
        self.show_tab("emojis")

    # --- contenido ---------------------------------------------------------

    def _font_for(self, tab: str, pixels: int) -> QFont:
        font = emoji_font() if tab == "emojis" else QFont(self.font())
        font.setPixelSize(pixels)
        return font

    def _sections(self) -> list[Section]:
        return self.catalog.emojis if self.tab == "emojis" else self.catalog.symbols

    def _recent(self) -> list[str]:
        in_tab = self.catalog.emoji_chars if self.tab == "emojis" else self.catalog.symbol_chars
        return [t for t in self.settings.recent if getattr(self.catalog.by_char.get(t), "char", None) in in_tab]

    def show_tab(self, tab: str):
        self.tab = tab
        self.tab_buttons[tab].setChecked(True)
        self.search.setPlaceholderText("Buscar emojis" if tab == "emojis" else "Buscar símbolos")
        if tab == "emojis":
            self.grid.setFont(self._font_for("emojis", 26))
            self.grid.setGridSize(QSize(42, 42))
        else:
            self.grid.setFont(self._font_for("simbolos", 20))
            self.grid.setGridSize(QSize(40, 40))
        self._build_footer()
        self.section_key = RECENT if self._recent() else self._sections()[0].key
        if self.search.text():
            self.search.clear()  # textChanged llama a refresh()
        else:
            self.refresh()

    def _build_footer(self):
        while self.footer.count():
            widget = self.footer.takeAt(0).widget()
            if widget is not None and widget is not self.tone_button:
                self.category_group.removeButton(widget)
                widget.deleteLater()
        entries = [(RECENT, "🕘", "Usados recientemente")]
        entries += [(s.key, s.icon, s.title) for s in self._sections()]
        for key, icon, title in entries:
            btn = QToolButton(self)
            btn.setText(shown(icon))
            btn.setToolTip(title)
            btn.setCheckable(True)
            btn.setProperty("key", key)
            btn.setObjectName("categoria")  # sin relleno: en macOS el emoji no cabría y saldría «…»
            btn.setFixedSize(32, 32)
            btn.setFont(self._font_for(self.tab if key != RECENT else "simbolos", 16))
            btn.clicked.connect(lambda _, k=key: self.show_section(k))
            self.category_group.addButton(btn)
            self.footer.addWidget(btn)
        self.footer.addStretch(1)
        if self.tab == "emojis":
            self._update_tone_button()
            self.footer.addWidget(self.tone_button)
            self.tone_button.show()
        else:
            self.tone_button.hide()

    def show_section(self, key: str):
        self.section_key = key
        if self.search.text():
            self.search.clear()  # refresh() lo llama textChanged
        else:
            self.refresh()
        self.search.setFocus()

    def refresh(self):
        query = self.search.text().strip()
        tone = self.settings.tone
        if query:
            items = [i for s in self._sections() for i in s.items]
            found = search(items, query)
            cells = [(i.with_tone(tone), i.name) for i in found]
            self.cells_items = list(found)
            title = f"Resultados de «{query}»"
        elif self.section_key == RECENT:
            texts = self._recent()
            cells = [(t, getattr(self.catalog.by_char.get(t), "name", "")) for t in texts]
            self.cells_items = [self.catalog.by_char.get(t) for t in texts]
            title = "Usados recientemente"
        else:
            section = next(s for s in self._sections() if s.key == self.section_key)
            cells = [(i.with_tone(tone), i.name) for i in section.items]
            self.cells_items = list(section.items)
            title = section.title
        for btn in self.category_group.buttons():
            btn.setChecked(not query and btn.property("key") == self.section_key)
        self.section_label.setText(title)
        self.grid.model_.set_cells(cells)
        self.grid.setVisible(bool(cells))
        self.empty.setText("Todavía no has usado ninguno" if self.section_key == RECENT and not query
                           else "No se encontró nada")
        self.empty.setVisible(not cells)
        if cells:
            self.grid.setCurrentIndex(self.grid.model_.index(0))
            self.grid.scrollToTop()

    # --- tono de piel ------------------------------------------------------

    def _tone_variants(self) -> list[str]:
        item = self.catalog.by_char.get(TONE_SAMPLE)
        return [TONE_SAMPLE, *(item.tones if item and item.tones else [])]

    def _update_tone_button(self):
        variants = self._tone_variants()
        self.tone_button.setText(shown(variants[min(self.settings.tone, len(variants) - 1)]))

    def _popup_menu(self, menu: QMenu, pos):
        self.menu_open = True
        try:
            return menu.exec(pos)
        finally:
            self.menu_open = False
            self.activateWindow()

    def _choose_tone(self):
        menu = QMenu(self)
        font = QFont(self.font())
        font.setPixelSize(15)
        menu.setFont(font)
        for tone, (variant, name) in enumerate(zip(self._tone_variants(), TONE_NAMES)):
            action = menu.addAction(f"{shown(variant)}  {name}")
            action.setData(tone)
            action.setCheckable(True)
            action.setChecked(tone == self.settings.tone)
        # Se abre hacia arriba, dentro del panel, como en Windows.
        corner = self.tone_button.mapToGlobal(self.tone_button.rect().topRight())
        size = menu.sizeHint()
        chosen = self._popup_menu(menu, QPoint(corner.x() - size.width(), corner.y() - size.height()))
        if chosen is not None:
            self.settings.set_tone(chosen.data())
            self._update_tone_button()
            self.refresh()

    def _tone_menu_for(self, row: int):
        """Clic derecho sobre un emoji con tonos: elegir el tono solo para esa vez."""
        item = self.cells_items[row] if row < len(self.cells_items) else None
        if item is None or not item.tones:
            return
        menu = QMenu(self)
        menu.setFont(self._font_for("emojis", 22))
        for variant in [item.char, *item.tones]:
            menu.addAction(shown(variant)).setData(variant)
        chosen = self._popup_menu(menu, QCursor.pos())
        if chosen is not None:
            self.choose(chosen.data())

    # --- teclado -----------------------------------------------------------

    def _focus_grid(self):
        if self.grid.isVisible():
            self.grid.setFocus()

    def _accept_first(self):
        index = self.grid.currentIndex()
        if self.grid.isVisible() and index.isValid():
            self.choose(index.data(Qt.ItemDataRole.UserRole))

    def _type_into_search(self, text: str):
        self.search.setFocus()
        self.search.insert(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    # --- abrir, elegir y cerrar -------------------------------------------

    def open(self, tab: str = "emojis"):
        if self.isVisible():
            # El mismo atajo otra vez cierra el panel; el otro cambia de pestaña.
            if tab == self.tab:
                self.hide()
            else:
                self.show_tab(tab)
                self.search.setFocus()
            return
        self.target = inserter.Target()  # antes de mostrarse, para saber a dónde volver
        self.setStyleSheet(_stylesheet())
        self.show_tab(tab)
        if config.IS_MACOS:
            from . import macos

            macos.activate_self()
        if QGuiApplication.platformName() in ("xcb", "cocoa"):
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            area = screen.availableGeometry()
            pos = QCursor.pos()
            x = min(max(pos.x() - WIDTH // 2, area.left() + 8), area.right() - WIDTH - 8)
            y = min(max(pos.y() + 16, area.top() + 8), area.bottom() - HEIGHT - 8)
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def choose(self, text: str):
        if not text:
            return
        self.settings.use(text)
        if inserter.method() == "portapapeles":
            inserter.copy_now(text)  # mientras el panel aún tiene el foco
        self.hide()
        # En macOS hay que esperar a que la otra app vuelva a estar delante.
        QTimer.singleShot(250 if config.IS_MACOS else 120, lambda: self._insert(text))

    def _insert(self, text: str):
        message = inserter.insert(text, self.target)
        if message:
            self.notify(f"{text}  {message}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.use_mask:
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), 10, 10)
            self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def changeEvent(self, event):
        super().changeEvent(event)
        # Como en Windows: al hacer clic fuera, el panel se cierra.
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow() and not self.menu_open:
            QTimer.singleShot(0, lambda: (not self.isActiveWindow() and not self.menu_open) and self.hide())
