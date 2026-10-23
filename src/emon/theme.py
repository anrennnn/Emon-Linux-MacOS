"""Colores y forma del panel sacados del escritorio, no copiados de Windows.

* Claro u oscuro: lo que diga el escritorio (GNOME, Cinnamon, XFCE o MATE guardan
  el tema en su configuración; en KDE Plasma y macOS lo sabe Qt).
* Color de acento: el de la paleta del sistema si Qt la conoce (KDE, macOS, GNOME
  con el tema de GTK para Qt); si no, el acento de GNOME 47+ o el que indica el
  nombre del tema (ZorinBlue, Mint-Y-Aqua, Yaru-olive…).
* Esquinas: como las ventanas de cada escritorio.
"""

import shutil
import subprocess

from . import config
from .qt import QColor, QGuiApplication

# Acentos de GNOME 47+ (org.gnome.desktop.interface accent-color), con los tonos de libadwaita.
GNOME_ACCENTS = {
    "blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800", "orange": "#ed5b00",
    "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac", "slate": "#6f8396",
}
# Palabras en nombres de temas de GTK (Zorin, Mint, Yaru, Pop…) y un tono parecido.
THEME_WORDS = {
    "aqua": "#1f9ede", "teal": "#2190a4", "blue": "#3584e4", "green": "#3a944a", "olive": "#4b8501",
    "sage": "#657b69", "orange": "#e95420", "red": "#e62d42", "magenta": "#b34cb3", "pink": "#d56199",
    "purple": "#9141ac", "grey": "#6f8396", "gray": "#6f8396", "brown": "#986a44", "sand": "#c8ac69",
    "yellow": "#c88800", "viridian": "#03875b", "prussiangreen": "#308280", "bark": "#787859",
    "yaru": "#e95420",  # Ubuntu sin color en el nombre: naranja
}
DEFAULT_ACCENT = "#3584e4"
# Qt usa este azul cuando no conoce el acento del sistema (estilo Fusion).
QT_FALLBACK_HIGHLIGHTS = {"#308cc6", "#3daee9"}

RADIUS = {"gnome": 12, "kde": 8, "cinnamon": 8, "xfce": 6, "mate": 6, "cosmic": 12}


def _read(*cmd) -> str:
    if not shutil.which(cmd[0]):
        return ""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.strip("'\"")


def _gtk_theme() -> tuple[str, str]:
    """(tema de GTK, preferencia de color de GNOME)."""
    desktop = config.desktop()
    if desktop == "cinnamon":
        return _read("gsettings", "get", "org.cinnamon.desktop.interface", "gtk-theme"), ""
    if desktop == "xfce":
        return _read("xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"), ""
    if desktop == "mate":
        return _read("gsettings", "get", "org.mate.interface", "gtk-theme"), ""
    if desktop in ("gnome", "cosmic", "desconocido") or "gnome" in desktop:
        return (
            _read("gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"),
            _read("gsettings", "get", "org.gnome.desktop.interface", "color-scheme"),
        )
    return "", ""


def _mix(a: QColor, b: QColor, amount: float) -> QColor:
    """amount de a y el resto de b."""
    return QColor(
        round(a.red() * amount + b.red() * (1 - amount)),
        round(a.green() * amount + b.green() * (1 - amount)),
        round(a.blue() * amount + b.blue() * (1 - amount)),
    )


class Theme:
    def __init__(self):
        palette = QGuiApplication.palette()
        window, base, text = palette.window().color(), palette.base().color(), palette.windowText().color()
        palette_dark = window.lightness() < 128

        desktop = config.desktop()
        gtk_theme, scheme = ("", "") if config.IS_MACOS or desktop == "kde" else _gtk_theme()
        if scheme == "prefer-dark":
            dark = True
        elif scheme == "prefer-light":
            dark = False
        elif gtk_theme:
            dark = "dark" in gtk_theme.lower()
        else:
            dark = palette_dark

        if dark == palette_dark:
            # La paleta de Qt ya es la del escritorio (KDE, macOS, GNOME con su tema para Qt).
            self.bg, self.field, self.text = window, base, text
        elif dark:
            self.bg, self.field, self.text = QColor("#242424"), QColor("#303030"), QColor("#ffffff")
        else:
            self.bg, self.field, self.text = QColor("#fafafa"), QColor("#ffffff"), QColor("#1e1e1e")
        self.dark = dark

        highlight = palette.highlight().color()
        accent = None
        if highlight.name() not in QT_FALLBACK_HIGHLIGHTS:
            accent = highlight
        if desktop == "gnome" or "gnome" in desktop:
            name = _read("gsettings", "get", "org.gnome.desktop.interface", "accent-color")
            if name in GNOME_ACCENTS:
                accent = QColor(GNOME_ACCENTS[name])
        if accent is None and gtk_theme:
            lowered = gtk_theme.lower().replace("-", "").replace("_", "")
            for word, color in THEME_WORDS.items():
                if word in lowered:
                    accent = QColor(color)
                    break
        self.accent = accent or QColor(DEFAULT_ACCENT)

        self.sub = _mix(self.text, self.bg, 0.6)
        self.border = _mix(self.text, self.bg, 0.14)
        self.hover = _mix(self.text, self.bg, 0.08)
        self.selected = _mix(self.accent, self.bg, 0.22)
        self.radius = 10 if config.IS_MACOS else RADIUS.get(desktop, 8)

    def palette(self):
        """Paleta de Qt con estos colores, para ventanas normales (la de ajustes)."""
        from .qt import QPalette

        palette = QPalette(QGuiApplication.palette())
        role = QPalette.ColorRole
        for roles, color in (
            ((role.Window, role.Button, role.AlternateBase), self.bg),
            ((role.Base,), self.field),
            ((role.WindowText, role.Text, role.ButtonText), self.text),
            ((role.Highlight,), self.accent),
            ((role.PlaceholderText,), self.sub),
        ):
            for r in roles:
                palette.setColor(r, color)
        return palette

    def stylesheet(self) -> str:
        r = self.radius
        small = max(r - 4, 4)
        c = {k: v.name() for k, v in vars(self).items() if isinstance(v, QColor)}
        return f"""
            #panel {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: {r}px; }}
            QLabel {{ color: {c['text']}; }}
            #section {{ color: {c['sub']}; font-weight: 600; padding: 2px 4px; }}
            #empty {{ color: {c['sub']}; }}
            QLineEdit {{ background: {c['field']}; color: {c['text']}; border: 1px solid {c['border']};
                         border-radius: {small}px; padding: 6px 8px; }}
            QLineEdit:focus {{ border: 2px solid {c['accent']}; padding: 5px 7px; }}
            QListView {{ background: transparent; border: none; outline: none; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 3px; min-height: 30px; }}
            QScrollBar::handle:vertical:hover {{ background: {c['sub']}; }}
            QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page
                {{ background: none; height: 0px; }}
            QToolButton {{ color: {c['text']}; background: transparent; border: none; border-radius: {small}px;
                           padding: 3px 6px; }}
            QToolButton:hover {{ background: {c['hover']}; }}
            QToolButton:checked {{ background: {c['selected']}; }}
            #tab {{ font-size: 14px; padding: 5px 10px; }}
            #categoria {{ padding: 0px; }}
            QMenu {{ background: {c['field']}; color: {c['text']}; border: 1px solid {c['border']};
                     border-radius: {small}px; }}
            QMenu::item {{ padding: 4px 14px; border-radius: {small}px; }}
            QMenu::item:selected {{ background: {c['selected']}; }}
        """
