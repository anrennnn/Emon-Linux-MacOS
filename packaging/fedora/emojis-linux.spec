Name:           emojis-linux
Version:        @VERSION@
Release:        1%{?dist}
Summary:        Panel de emojis y símbolos al estilo de Windows (Super+.)
License:        MIT AND Unicode-3.0
URL:            https://github.com/anrennnn/EMON-Linux-MacOS
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  make
Requires:       python3
Requires:       python3-pyqt6
Requires:       python3-gobject
Requires:       google-noto-color-emoji-fonts
Requires:       libnotify
Recommends:     xdotool
Recommends:     wtype
Suggests:       ydotool

%description
Super+. (o Super+;) abre un panel con todos los emojis de Unicode, por
categorías, con búsqueda en el idioma del sistema y en inglés, usados
recientemente y tonos de piel. El emoji elegido se escribe en la aplicación
que tenía el foco. Incluye una pestaña de símbolos.

Funciona en KDE Plasma, GNOME, Cinnamon y XFCE, en X11 y Wayland.

%prep
%autosetup

%build
# Nada que compilar: es Python.

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix} SYSCONFDIR=%{_sysconfdir} \
    DOCDIR=%{_licensedir}/%{name}

%files
%license %{_licensedir}/%{name}/LICENSE
%license %{_licensedir}/%{name}/LICENSE-UNICODE
%{_bindir}/emojis-linux
%{_prefix}/lib/%{name}/
%{_datadir}/applications/emojis-linux.desktop
%{_datadir}/icons/hicolor/scalable/apps/emojis-linux.svg
%config(noreplace) %{_sysconfdir}/xdg/autostart/emojis-linux.desktop

%changelog
* Fri Oct 23 2026 Emojis-Linux <emojis-linux@users.noreply.github.com> - 0.2.0-1
- Pega solo en GNOME y KDE con Wayland (portal RemoteDesktop) y recupera el portapapeles.
- Colores del escritorio (claro/oscuro, acento) y ventana para elegir el atajo.
* Fri Oct 23 2026 Emojis-Linux <emojis-linux@users.noreply.github.com> - 0.1.0-1
- Primera versión: emojis de Unicode 18.0, símbolos, búsqueda y tonos de piel.
