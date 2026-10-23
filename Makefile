# Instalación común a todos los paquetes (.deb, .rpm, Arch/CachyOS) y a `sudo make install`.
#
#   make install DESTDIR=/ruta/paquete PREFIX=/usr DOCDIR=/usr/share/licenses/emon
#
# El código se instala en un directorio propio y no en site-packages, así el
# paquete sigue funcionando cuando la distribución actualiza Python (en Arch y
# Fedora eso pasa a menudo).

PREFIX  ?= /usr
SYSCONFDIR ?= /etc
LIBDIR  ?= $(PREFIX)/lib/emon
DOCDIR  ?= $(PREFIX)/share/doc/emon
LICENSE_NAME ?= LICENSE
DESTDIR ?=

PKG = $(DESTDIR)$(LIBDIR)/emon

.PHONY: install uninstall

install:
	install -d "$(PKG)/datos/nombres"
	install -m 644 src/emon/*.py "$(PKG)/"
	install -m 644 src/emon/datos/*.json "$(PKG)/datos/"
	install -m 644 src/emon/datos/nombres/*.json.gz "$(PKG)/datos/nombres/"
	install -d "$(DESTDIR)$(PREFIX)/bin"
	printf '%s\n' '#!/bin/sh' \
	    'export PYTHONPATH="$(LIBDIR)$${PYTHONPATH:+:$$PYTHONPATH}"' \
	    'exec /usr/bin/python3 -m emon "$$@"' > "$(DESTDIR)$(PREFIX)/bin/emon"
	chmod 755 "$(DESTDIR)$(PREFIX)/bin/emon"
	install -Dm 644 data/applications/emon.desktop "$(DESTDIR)$(PREFIX)/share/applications/emon.desktop"
	install -Dm 644 data/autostart/emon.desktop "$(DESTDIR)$(SYSCONFDIR)/xdg/autostart/emon.desktop"
	install -Dm 644 data/icons/emon.svg "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/emon.svg"
	install -Dm 644 LICENSE "$(DESTDIR)$(DOCDIR)/$(LICENSE_NAME)"
	install -Dm 644 LICENSE-UNICODE "$(DESTDIR)$(DOCDIR)/LICENSE-UNICODE"

uninstall:
	rm -rf "$(DESTDIR)$(LIBDIR)" "$(DESTDIR)$(DOCDIR)"
	rm -f "$(DESTDIR)$(PREFIX)/bin/emon" \
	      "$(DESTDIR)$(PREFIX)/share/applications/emon.desktop" \
	      "$(DESTDIR)$(SYSCONFDIR)/xdg/autostart/emon.desktop" \
	      "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/emon.svg"
