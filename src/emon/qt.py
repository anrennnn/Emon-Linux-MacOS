"""Qt para el resto de la app: PyQt6 si está instalado y, si no, PyQt5.

Ubuntu 22.04 y lo que se basa en él (Linux Mint 21, Zorin OS 17, Pop!_OS 22.04)
no tienen PyQt6 en sus repositorios. Con PyQt5 5.15 el mismo código funciona
porque admite los enums con su nombre completo (Qt.AlignmentFlag.AlignCenter).
"""

try:
    from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets

    QT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets

    QT6 = False

_EXPORTS = {
    QtCore: "QAbstractListModel QModelIndex QPoint QRectF QSize Qt QTimer pyqtSignal",
    QtGui: "QColor QCursor QFont QFontDatabase QGuiApplication QKeySequence QPainter QPainterPath "
           "QPalette QRegion QTextLayout",
    QtNetwork: "QLocalServer QLocalSocket",
    QtWidgets: "QAbstractItemView QApplication QButtonGroup QDialog QFrame QHBoxLayout QKeySequenceEdit "
               "QLabel QLineEdit QListView QMenu QPushButton QStyle QStyledItemDelegate QToolButton "
               "QVBoxLayout QWidget",
}
for _module, _names in _EXPORTS.items():
    for _name in _names.split():
        globals()[_name] = getattr(_module, _name)


def font_families() -> list[str]:
    # En Qt 6 es un método estático; en Qt 5 hay que crear la base de datos.
    return list(QtGui.QFontDatabase.families() if QT6 else QtGui.QFontDatabase().families())


def first_key(sequence) -> tuple[int, int]:
    """(tecla, modificadores) de la primera combinación de un QKeySequence."""
    if sequence.isEmpty():
        return 0, 0
    combo = sequence[0]
    if QT6:
        return int(combo.key().value), int(combo.keyboardModifiers().value)
    combo = int(combo)
    mods = combo & 0xFE000000
    return combo & ~0xFE000000, mods


def combined(sequence) -> int:
    """La primera combinación como entero (tecla | modificadores), como la guarda KDE."""
    key, mods = first_key(sequence)
    return key | mods


def prepare_application():
    """Ajustes que hay que hacer antes de crear QApplication."""
    if not QT6:
        QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
