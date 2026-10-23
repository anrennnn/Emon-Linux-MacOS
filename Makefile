# Instalación común a todos los paquetes (.deb, .rpm, Arch/CachyOS) y a `sudo make install`.
#
#   make install DESTDIR=/ruta/paquete PREFIX=/usr DOCDIR=/usr/share/licenses/emojis-linux
#
# El código se instala en un directorio propio y no en site-packages, así el
# paquete sigue funcionando cuando la distribución actualiza Python (en Arch y
# Fedora eso pasa a menudo).

PREFIX  ?= /usr
SYSCONFDIR ?= /etc
LIBDIR  ?= $(PREFIX)/lib/emojis-linux
DOCDIR  ?= $(PREFIX)/share/doc/emojis-linux
LICENSE_NAME ?= LICENSE
DESTDIR ?=

PKG = $(DESTDIR)$(LIBDIR)/emojis_linux

.PHONY: install uninstall

install:
	install -d "$(PKG)/datos/nombres"
	install -m 644 src/emojis_linux/*.py "$(PKG)/"
	install -m 644 src/emojis_linux/datos/*.json "$(PKG)/datos/"
	install -m 644 src/emojis_linux/datos/nombres/*.json.gz "$(PKG)/datos/nombres/"
	install -d "$(DESTDIR)$(PREFIX)/bin"
	printf '%s\n' '#!/bin/sh' \
	    'export PYTHONPATH="$(LIBDIR)$${PYTHONPATH:+:$$PYTHONPATH}"' \
	    'exec /usr/bin/python3 -m emojis_linux "$$@"' > "$(DESTDIR)$(PREFIX)/bin/emojis-linux"
	chmod 755 "$(DESTDIR)$(PREFIX)/bin/emojis-linux"
	install -Dm 644 data/applications/emojis-linux.desktop "$(DESTDIR)$(PREFIX)/share/applications/emojis-linux.desktop"
	install -Dm 644 data/autostart/emojis-linux.desktop "$(DESTDIR)$(SYSCONFDIR)/xdg/autostart/emojis-linux.desktop"
	install -Dm 644 data/icons/emojis-linux.svg "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/emojis-linux.svg"
	install -Dm 644 LICENSE "$(DESTDIR)$(DOCDIR)/$(LICENSE_NAME)"
	install -Dm 644 LICENSE-UNICODE "$(DESTDIR)$(DOCDIR)/LICENSE-UNICODE"

uninstall:
	rm -rf "$(DESTDIR)$(LIBDIR)" "$(DESTDIR)$(DOCDIR)"
	rm -f "$(DESTDIR)$(PREFIX)/bin/emojis-linux" \
	      "$(DESTDIR)$(PREFIX)/share/applications/emojis-linux.desktop" \
	      "$(DESTDIR)$(SYSCONFDIR)/xdg/autostart/emojis-linux.desktop" \
	      "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/emojis-linux.svg"
