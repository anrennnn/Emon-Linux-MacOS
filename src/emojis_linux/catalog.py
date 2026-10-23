"""Emojis y símbolos disponibles, con sus nombres en el idioma del sistema y en inglés.

Los datos vienen de Unicode (emoji-test.txt) y CLDR; se generan con
herramientas/generar_datos.py.
"""

import gzip
import json
import os
import unicodedata
from dataclasses import dataclass, field

from . import config

ZWJ, VS16 = "‍", "️"

# Fuentes de emoji en color más comunes, por orden de preferencia.
EMOJI_FONTS = (
    "Noto Color Emoji", "Twemoji", "Twitter Color Emoji", "JoyPixels", "EmojiOne Color",
    "OpenMoji Color", "Apple Color Emoji", "Segoe UI Emoji", "Blobmoji",
)


@dataclass
class Item:
    char: str
    tones: list[str] = field(default_factory=list)  # 5 variantes, de claro a oscuro
    name: str = ""  # en el idioma del sistema (o inglés)
    search: str = ""  # nombres y palabras clave normalizados, separados por espacios
    names: list[str] = field(default_factory=list)  # nombres normalizados en cada idioma

    def with_tone(self, tone: int) -> str:
        return self.tones[tone - 1] if tone and self.tones else self.char


@dataclass
class Section:
    key: str
    title: str
    icon: str
    items: list[Item]


# Icono de la barra inferior para cada grupo (como en el panel de Windows).
EMOJI_ICONS = {
    "caras": "😀", "personas": "🧑", "naturaleza": "🐻", "comida": "🍔", "viajes": "🚗",
    "actividades": "⚽", "objetos": "💡", "simbolos": "💟", "banderas": "🏳️",
}
SYMBOL_ICONS = {
    "puntuacion": "§", "moneda": "€", "latinos": "Á", "geometricos": "■",
    "matematicos": "∑", "complementarios": "→", "idioma": "Ω",
}


def normalize(text: str) -> str:
    """Minúsculas y sin tildes, para que «corazon» encuentre «corazón»."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def system_locales() -> list[str]:
    """Idiomas para buscar, del más concreto al más general, con el inglés al final.

    es_MX.UTF-8 → es-MX, es-419, es, en
    """
    available = {p.name.removesuffix(".json.gz") for p in (config.DATA_FILES / "nombres").glob("*.json.gz")}
    result = []
    for var in ("EMOJIS_LINUX_IDIOMA", "LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        for raw in (os.environ.get(var) or "").split(":"):
            raw = raw.split(".")[0].split("@")[0]
            if not raw or raw in ("C", "POSIX"):
                continue
            lang, _, region = raw.replace("-", "_").partition("_")
            candidates = [f"{lang}-{region}"] if region else []
            if lang == "es" and region not in ("", "ES"):
                candidates.append("es-419")  # español de América
            if lang == "pt" and region == "PT":
                candidates.append("pt-PT")
            if lang == "zh" and region in ("TW", "HK", "MO"):
                candidates.append("zh-Hant")
            candidates.append(lang)
            result += [c for c in candidates if c in available and c not in result]
        if result:
            break
    if not result and config.IS_MACOS:
        from .macos import system_locale

        os.environ.setdefault("EMOJIS_LINUX_IDIOMA", system_locale())
        if os.environ["EMOJIS_LINUX_IDIOMA"]:
            return system_locales()
    if "en" not in result:
        result.append("en")
    return result


def _load_names(locale: str) -> dict[str, str]:
    path = config.DATA_FILES / "nombres" / f"{locale}.json.gz"
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


class Catalog:
    def __init__(self, locales: list[str] | None = None):
        self.locales = locales or system_locales()
        tables = [_load_names(loc) for loc in self.locales]

        emoji_data = json.loads((config.DATA_FILES / "emojis.json").read_text(encoding="utf-8"))
        symbol_data = json.loads((config.DATA_FILES / "simbolos.json").read_text(encoding="utf-8"))
        self.emoji_version = emoji_data["version"]

        def make(char: str, english: str = "", tones=None) -> Item:
            entries = [t[char] for t in tables if char in t]
            names = [e.split("|")[0] for e in entries] + ([english] if english else [])
            words = " ".join(entries) + " " + english
            return Item(char, list(tones or []), names[0] if names else "",
                        normalize(words.replace("|", " ")), [normalize(n) for n in names])

        self.emojis = [
            Section(g["clave"], g["nombre"], EMOJI_ICONS.get(g["clave"], "•"),
                    [make(e["e"], e["n"], e.get("t")) for e in g["emojis"]])
            for g in emoji_data["grupos"]
        ]
        self.symbols = [
            Section(g["clave"], g["nombre"], SYMBOL_ICONS.get(g["clave"], "•"),
                    [make(c) for c in g["simbolos"]])
            for g in symbol_data["grupos"]
        ]
        self.emoji_chars = {i.char for s in self.emojis for i in s.items}
        self.symbol_chars = {i.char for s in self.symbols for i in s.items}
        self.by_char = {}
        for section in self.emojis + self.symbols:
            for item in section.items:
                self.by_char.setdefault(item.char, item)
                for tone in item.tones:
                    self.by_char.setdefault(tone, item)

    def drop_unsupported(self, supported):
        """Quita los emojis que la fuente del sistema no sabe dibujar (saldrían como cajas)."""
        hidden = 0
        for section in self.emojis:
            keep = []
            for item in section.items:
                if supported(item.char):
                    if item.tones and not supported(item.tones[-1]):
                        item.tones = []
                    keep.append(item)
                else:
                    hidden += 1
            section.items = keep
        self.emoji_chars = {i.char for s in self.emojis for i in s.items}
        return hidden


def search(items: list[Item], query: str, limit: int = 300) -> list[Item]:
    """Cada palabra de la búsqueda tiene que ser el principio de alguna palabra del nombre."""
    words = normalize(query).split()
    phrase = " ".join(words)
    if not words:
        return []
    scored = []
    for order, item in enumerate(items):
        haystack = " " + item.search
        if not all(f" {w}" in haystack for w in words):
            continue
        # Primero los que se llaman así, luego los que empiezan así, y al final
        # los que solo lo tienen como palabra clave. A igualdad, el nombre más corto
        # y después el de nombres más cortos en todos los idiomas, que suele ser el más
        # básico: «corazón rojo» (red heart) va antes que «corazón roto» (broken heart).
        best = (4, 0)
        for name in item.names:
            if name == phrase:
                rank = 0
            elif name.startswith(phrase):
                rank = 1
            elif all(f" {w}" in " " + name for w in words):
                rank = 2
            else:
                rank = 3
            best = min(best, (rank, len(name)))
        scored.append(((*best, sum(map(len, item.names))), order, item))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [item for _, _, item in scored[:limit]]
