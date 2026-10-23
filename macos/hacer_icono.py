"""Convierte data/icons/emojis-linux.svg en el iconset que iconutil pasa a .icns."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

svg, out = Path(sys.argv[1]), Path(sys.argv[2])
app = QGuiApplication(sys.argv[:1])
renderer = QSvgRenderer(str(svg))
out.mkdir(parents=True, exist_ok=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        px = size * scale
        image = QImage(px, px, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        suffix = "" if scale == 1 else "@2x"
        image.save(str(out / f"icon_{size}x{size}{suffix}.png"))
