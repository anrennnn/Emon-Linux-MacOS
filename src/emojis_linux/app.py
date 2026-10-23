"""Proceso en segundo plano y comandos de Emojis.

Un único proceso por usuario tiene los emojis cargados y muestra el panel al
instante. El atajo Super+. lanza `emojis-linux abrir`, que solo envía la orden
por un socket local y termina. Si el proceso de fondo no está corriendo, el
primero que se lance se convierte en él.
"""

import argparse
import os
import shutil
import subprocess
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

from . import config

SOCKET_NAME = f"{config.APP_ID}-{os.getuid()}"


def send_to_daemon(command: str) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(500):
        return False
    sock.write(command.encode() + b"\n")
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


class Daemon:
    def __init__(self, app: QApplication):
        from .catalog import Catalog
        from .picker import EmojiPanel, emoji_font, support_checker

        self.app = app
        catalog = Catalog()
        hidden = catalog.drop_unsupported(support_checker(emoji_font()))
        if hidden:
            print(f"{hidden} emojis ocultos: la fuente de emojis instalada todavía no los incluye.", file=sys.stderr)
        self.panel = EmojiPanel(catalog, config.Settings(), lambda text: notify(config.APP_NAME, text))
        self.hotkeys = None
        if config.IS_MACOS:
            from . import macos

            macos.become_accessory()
            self.hotkeys = macos.HotKeys(lambda: self.handle("abrir"))

        QLocalServer.removeServer(SOCKET_NAME)
        self.server = QLocalServer()
        self.server.newConnection.connect(self._on_connection)
        if not self.server.listen(SOCKET_NAME):
            print("No se pudo abrir el socket de control:", self.server.errorString(), file=sys.stderr)

    def _on_connection(self):
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._read(c))

    def _read(self, conn):
        while conn.canReadLine():
            self.handle(bytes(conn.readLine()).decode().strip())

    def handle(self, command: str):
        if command == "abrir":
            self.panel.open("emojis")
        elif command == "simbolos":
            self.panel.open("simbolos")
        elif command == "salir":
            self.app.quit()


def notify(title: str, body: str):
    if config.IS_MACOS:
        from . import macos

        macos.notify(title, body)
        return
    if not shutil.which("notify-send"):
        print(f"{title}: {body}")
        return
    subprocess.Popen([
        "notify-send", "--app-name", config.APP_NAME, "--icon", config.APP_ID,
        "--expire-time", "4000", "--hint", "int:transient:1", title, body,
    ])


def _prepare_platform():
    if config.IS_MACOS:
        return
    # En GNOME y Cinnamon con Wayland, una ventana nativa no puede colocarse junto al
    # puntero ni sabe a qué ventana volver; con XWayland sí (igual que en Cutter).
    if (
        config.session_type() == "wayland"
        and config.desktop() in ("gnome", "cinnamon")
        and os.environ.get("DISPLAY")
        and "QT_QPA_PLATFORM" not in os.environ
    ):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="emojis-linux",
        description="Panel de emojis y símbolos al estilo de Windows (Super+. en Linux, ⌃⌘. en macOS).",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("abrir", help="Abrir el panel de emojis (Super+.)")
    sub.add_parser("simbolos", help="Abrir el panel en la pestaña de símbolos")
    sub.add_parser("segundo-plano", help="Iniciar solo el proceso de fondo (se usa al iniciar sesión)")
    sub.add_parser("atajos", help="Volver a configurar Super+. en el escritorio (Linux)")
    sub.add_parser("salir", help="Detener el proceso de fondo")
    sub.add_parser("version", help="Mostrar la versión")
    args = parser.parse_args(argv)

    if args.command == "version":
        from .catalog import Catalog

        print(config.APP_NAME, config.VERSION, f"(Emoji {Catalog(['en']).emoji_version})")
        return 0
    if args.command == "atajos" and not config.IS_MACOS:
        from .shortcuts import setup_shortcuts

        for line in setup_shortcuts(force=True):
            print(line)
        return 0

    # Sin argumentos (menú de aplicaciones o Emojis.app en el Finder) se abre el panel;
    # al iniciar sesión se usa «segundo-plano», que solo deja el proceso listo.
    command = {"abrir": "abrir", "simbolos": "simbolos", "salir": "salir"}.get(args.command or "abrir", "")

    _prepare_platform()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(config.APP_ID)
    app.setApplicationDisplayName(config.APP_NAME)
    app.setDesktopFileName(config.APP_ID)
    app.setQuitOnLastWindowClosed(False)

    if command and send_to_daemon(command):
        return 0
    if args.command == "salir":
        return 0
    if args.command == "segundo-plano" and send_to_daemon("ping"):
        return 0  # ya hay uno corriendo

    if config.IS_MACOS:
        from .macos import setup_login_item

        messages = setup_login_item()
    else:
        from .shortcuts import setup_shortcuts

        messages = setup_shortcuts()
    daemon = Daemon(app)
    if messages:
        notify(config.APP_NAME, "\n".join(messages))
    if command:
        QTimer.singleShot(100, lambda: daemon.handle(command))
    return app.exec()
