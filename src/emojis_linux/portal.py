"""Pegar solo en GNOME y KDE Plasma con Wayland, con el portal RemoteDesktop.

En Wayland, GNOME y KDE no dejan que un programa teclee en la ventana de otro.
La vía oficial es el portal org.freedesktop.portal.RemoteDesktop: la primera vez
el escritorio pregunta al usuario si Emojis puede controlar el teclado, y
después Emojis pulsa Ctrl+V por él. Los emojis no se pueden teclear directamente
(GNOME solo acepta teclas que existan en la distribución del teclado), así que
se copia el emoji y se pega.

Donde el portal guarda el permiso (versión 2 o más reciente), se pide una sola
vez; en versiones anteriores, una vez por sesión.

Usa Gio (PyGObject). Qt en Linux corre sobre el bucle de eventos de GLib, así
que las respuestas del portal llegan sin hilos ni bucles propios.
"""

import secrets

try:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError):
    Gio = GLib = None

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJECT_PATH = "/org/freedesktop/portal/desktop"
REMOTE_DESKTOP = "org.freedesktop.portal.RemoteDesktop"
KEYBOARD = 1
PERSIST_UNTIL_REVOKED = 2

XK_CONTROL_L, XK_V = 0xFFE3, 0x0076


class RemoteKeyboard:
    def __init__(self, load_token, save_token):
        """load_token() y save_token(texto) guardan el permiso entre sesiones."""
        self.load_token = load_token
        self.save_token = save_token
        self.bus = None
        self.version = 0
        self.checked = False  # la consulta de versión se hace una sola vez
        self.session = ""
        self.starting = False
        self.waiting = []  # funciones a las que avisar cuando haya sesión (o falle)

    def available(self) -> bool:
        if Gio is None:
            return False
        if not self.checked:
            self.checked = True
            try:
                self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                reply = self.bus.call_sync(
                    BUS_NAME, OBJECT_PATH, "org.freedesktop.DBus.Properties", "Get",
                    GLib.Variant("(ss)", (REMOTE_DESKTOP, "version")),
                    GLib.VariantType.new("(v)"), Gio.DBusCallFlags.NONE, 2000, None,
                )
                self.version = reply.unpack()[0]
            except GLib.Error:
                self.bus = None
                self.version = 0
        return self.version > 0

    # --- pegar ------------------------------------------------------------

    def paste(self, done):
        """Pulsa Ctrl+V en la ventana activa. done(True/False) al terminar."""
        if self.session:
            done(self._send_paste())
            return
        self.waiting.append(done)
        if not self.starting:
            self.starting = True
            self._create_session()

    def _send_paste(self) -> bool:
        try:
            for keysym, pressed in ((XK_CONTROL_L, 1), (XK_V, 1), (XK_V, 0), (XK_CONTROL_L, 0)):
                self.bus.call_sync(
                    BUS_NAME, OBJECT_PATH, REMOTE_DESKTOP, "NotifyKeyboardKeysym",
                    GLib.Variant("(oa{sv}iu)", (self.session, {}, keysym, pressed)),
                    None, Gio.DBusCallFlags.NONE, 2000, None,
                )
            return True
        except GLib.Error as exc:
            print("El portal no aceptó la pulsación:", exc.message)
            self.session = ""  # la sesión se cerró: la próxima vez se pide otra
            return False

    def _finish_start(self, ok: bool):
        self.starting = False
        waiting, self.waiting = self.waiting, []
        for done in waiting:
            done(self._send_paste() if ok else False)

    # --- sesión del portal (CreateSession → SelectDevices → Start) ------------

    def _create_session(self):
        options = {"session_handle_token": GLib.Variant("s", _token())}
        self._request("CreateSession", "(a{sv})", lambda token: ({**options, "handle_token": token},),
                      self._session_created)

    def _session_created(self, results):
        self.session = str(results.get("session_handle", ""))
        if not self.session:
            self._finish_start(False)
            return
        self.bus.signal_subscribe(
            BUS_NAME, "org.freedesktop.portal.Session", "Closed", self.session, None,
            Gio.DBusSignalFlags.NONE, self._session_closed,
        )
        options = {"types": GLib.Variant("u", KEYBOARD)}
        if self.version >= 2:
            options["persist_mode"] = GLib.Variant("u", PERSIST_UNTIL_REVOKED)
            saved = self.load_token()
            if saved:
                options["restore_token"] = GLib.Variant("s", saved)
        self._request("SelectDevices", "(oa{sv})",
                      lambda token: (self.session, {**options, "handle_token": token}),
                      self._devices_selected)

    def _devices_selected(self, _results):
        # Aquí el escritorio enseña el aviso de permiso (si no hay uno guardado).
        self._request("Start", "(osa{sv})", lambda token: (self.session, "", {"handle_token": token}),
                      self._started)

    def _started(self, results):
        token = results.get("restore_token")
        if token:
            self.save_token(str(token))
        self._finish_start(bool(int(results.get("devices", 0)) & KEYBOARD))

    def _session_closed(self, *_args):
        self.session = ""

    def _request(self, method: str, signature: str, make_args, on_success):
        """Llama a un método del portal y espera su señal Response."""
        handle = _token()
        sender = self.bus.get_unique_name().lstrip(":").replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{handle}"
        subscription = None

        def on_response(_conn, _sender, _path, _iface, _signal, params):
            self.bus.signal_unsubscribe(subscription)
            code, results = params.unpack()
            if code == 0:
                on_success(results)
            else:  # 1 = el usuario dijo que no, 2 = otro error
                if method != "CreateSession":
                    self.session = ""
                self._finish_start(False)

        # Hay que suscribirse antes de llamar, o la respuesta podría llegar antes.
        subscription = self.bus.signal_subscribe(
            BUS_NAME, "org.freedesktop.portal.Request", "Response", path, None,
            Gio.DBusSignalFlags.NONE, on_response,
        )
        args = make_args(GLib.Variant("s", handle))

        def on_called(bus, result):
            try:
                bus.call_finish(result)
            except GLib.Error as exc:
                print(f"El portal falló en {method}:", exc.message)
                self.bus.signal_unsubscribe(subscription)
                self.session = ""
                self._finish_start(False)

        self.bus.call(
            BUS_NAME, OBJECT_PATH, REMOTE_DESKTOP, method, GLib.Variant(signature, args),
            None, Gio.DBusCallFlags.NONE, -1, None, on_called,
        )


def _token() -> str:
    return "emojis_" + secrets.token_hex(6)
