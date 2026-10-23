#!/usr/bin/env python3
"""Genera los datos de src/emojis_linux/datos a partir de Unicode y CLDR.

Uso:
    herramientas/generar_datos.py EMOJI_TEST CLDR_FULL CLDR_DERIVED

  EMOJI_TEST    emoji-test.txt de la versión de Emoji que se quiera incluir
                (github.com/unicode-org/unicodetools, unicodetools/data/emoji/<versión>/)
  CLDR_FULL     carpeta «annotations» del paquete npm cldr-annotations-full
  CLDR_DERIVED  carpeta «annotationsDerived» del paquete npm cldr-annotations-derived-full

Salida:
  datos/emojis.json         grupos, emojis y variantes de tono de piel (orden de Unicode)
  datos/simbolos.json       pestaña de símbolos, por categorías como en Windows
  datos/nombres/<idioma>.json.gz   nombre y palabras clave de cada emoji y símbolo
"""

import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "emojis_linux" / "datos"

TONES = "\U0001F3FB\U0001F3FC\U0001F3FD\U0001F3FE\U0001F3FF"
VS16 = "️"

# Grupos de emoji-test.txt → (clave, nombre que se muestra). «Component» no se enseña.
GROUPS = {
    "Smileys & Emotion": ("caras", "Caras y emociones"),
    "People & Body": ("personas", "Personas"),
    "Animals & Nature": ("naturaleza", "Animales y naturaleza"),
    "Food & Drink": ("comida", "Comida y bebida"),
    "Travel & Places": ("viajes", "Viajes y lugares"),
    "Activities": ("actividades", "Actividades"),
    "Objects": ("objetos", "Objetos"),
    "Symbols": ("simbolos", "Símbolos"),
    "Flags": ("banderas", "Banderas"),
}

LINE = re.compile(r"^([0-9A-F ]+?)\s*;\s*fully-qualified\s*#\s*\S+\s+E(\d+\.\d+)\s+(.*)$")


def parse_emoji_test(path: Path):
    groups, version = [], ""
    by_base = {}
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("# Version:"):
            version = raw.split(":", 1)[1].strip()
        if raw.startswith("# group:"):
            name = raw.split(":", 1)[1].strip()
            current = None
            if name in GROUPS:
                key, label = GROUPS[name]
                current = {"clave": key, "nombre": label, "emojis": []}
                groups.append(current)
            continue
        m = LINE.match(raw)
        if not m or current is None:
            continue
        char = "".join(chr(int(cp, 16)) for cp in m.group(1).split())
        tones = [c for c in char if c in TONES]
        if not tones:
            entry = {"e": char, "n": m.group(3), "v": m.group(2)}
            current["emojis"].append(entry)
            by_base[char] = entry
            continue
        # Igual que Windows: solo variantes con un único tono para toda la secuencia
        # (en 🧑🏻‍🤝‍🧑🏿, con tonos distintos, se queda fuera).
        if len(set(tones)) != 1:
            continue
        base = "".join(c for c in char if c not in TONES)
        entry = by_base.get(base) or by_base.get(base.replace(VS16, ""))
        if entry is None:
            # Algunas bases llevan VS16 que desaparece al poner el tono (🖐️ → 🖐🏻).
            entry = next((e for b, e in by_base.items() if b.replace(VS16, "") == base.replace(VS16, "")), None)
        if entry is not None:
            entry.setdefault("t", [""] * 5)[TONES.index(tones[0])] = char
    for g in groups:
        for e in g["emojis"]:
            if "t" in e and "" in e["t"]:
                del e["t"]  # variantes incompletas: mejor no ofrecer tonos
    return version, groups


def _chars(*ranges):
    out = []
    for item in ranges:
        if isinstance(item, str):
            out.extend(item)
            continue
        lo, hi = item
        for cp in range(lo, hi + 1):
            c = chr(cp)
            if unicodedata.category(c) not in ("Cn", "Co", "Cs", "Cc", "Cf", "Mn", "Zs"):
                out.append(c)
    seen, result = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


# Las mismas secciones que la pestaña «Símbolos» de Windows 11.
SYMBOL_SECTIONS = [
    ("puntuacion", "Puntuación general", _chars(
        "!\"#%&'()*,-./:;?@[\\]_{}¡§«¶·»¿", (0x2010, 0x2027), (0x2030, 0x205E))),
    ("moneda", "Símbolos de moneda", _chars("$¢£¤¥", (0x20A0, 0x20C1))),
    ("latinos", "Símbolos latinos", _chars((0x00C0, 0x00FF), (0x0100, 0x017F), "ªºƒǅ")),
    ("geometricos", "Símbolos geométricos", _chars((0x25A0, 0x25FF), (0x2B12, 0x2B2F))),
    ("matematicos", "Símbolos matemáticos", _chars(
        "+<=>|~¬±×÷°µ¹²³¼½¾", (0x2070, 0x209C), (0x2150, 0x218B), (0x2200, 0x22FF))),
    ("complementarios", "Símbolos complementarios", _chars(
        "©®™℃℉№℗℠Ω℮", (0x2190, 0x21FF), (0x2460, 0x24FF), (0x2600, 0x26FF), (0x2700, 0x27BF))),
    ("idioma", "Símbolos de idioma", _chars((0x0391, 0x03C9), (0x0410, 0x044F))),
]


def load_cldr(folder: Path, kind: str):
    """{idioma: {carácter: (nombre, [palabras clave])}}"""
    result = {}
    for loc_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
        data = json.loads((loc_dir / "annotations.json").read_text(encoding="utf-8"))
        ann = data.get(kind, {}).get("annotations") or {}
        result[loc_dir.name] = {
            k: ((v.get("tts") or [""])[0], v.get("default") or []) for k, v in ann.items()
        }
    return result


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    version, groups = parse_emoji_test(Path(argv[1]))
    full = load_cldr(Path(argv[2]), "annotations")
    derived = load_cldr(Path(argv[3]), "annotationsDerived")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nombres").mkdir(exist_ok=True)
    for old in (OUT / "nombres").glob("*.json.gz"):
        old.unlink()

    chars = [e["e"] for g in groups for e in g["emojis"]]
    symbols = [c for _, _, items in SYMBOL_SECTIONS for c in items]

    # Nombres en inglés de respaldo para los símbolos que CLDR no tiene.
    fallback = {c: unicodedata.name(c, "").lower() for c in symbols}

    written = 0
    for loc in sorted(set(full) | set(derived)):
        table = {**derived.get(loc, {}), **full.get(loc, {})}
        names = {}
        for c in chars + symbols:
            hit = table.get(c) or table.get(c.replace(VS16, ""))
            if hit is None:
                continue
            name, keywords = hit
            kws = [k for k in keywords if k.lower() != name.lower()]
            names[c] = "|".join([name, *kws])
        if loc == "en":
            for c, name in fallback.items():
                names.setdefault(c, name)
        # Idiomas con muy pocas traducciones (variantes regionales casi vacías) no aportan.
        if len(names) < 200:
            continue
        with gzip.open(OUT / "nombres" / f"{loc}.json.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
            json.dump(names, fh, ensure_ascii=False, separators=(",", ":"))
        written += 1

    (OUT / "emojis.json").write_text(
        json.dumps({"version": version, "grupos": groups}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (OUT / "simbolos.json").write_text(
        json.dumps(
            {"grupos": [{"clave": k, "nombre": n, "simbolos": "".join(items)} for k, n, items in SYMBOL_SECTIONS]},
            ensure_ascii=False, separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    total = sum(len(g["emojis"]) for g in groups)
    tones = sum(1 for g in groups for e in g["emojis"] if "t" in e)
    print(f"Emoji {version}: {total} emojis ({tones} con tonos de piel), {len(symbols)} símbolos, {written} idiomas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
