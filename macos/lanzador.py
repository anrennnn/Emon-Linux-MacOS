"""Punto de entrada de Emon.app (PyInstaller).

No se llama emon.py: si no, «import emon» encontraría este archivo en vez del paquete.
"""

import sys

from emon.app import main

sys.exit(main())
