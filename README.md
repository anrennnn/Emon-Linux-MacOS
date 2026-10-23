# Emojis para Linux y macOS

El panel de emojis de Windows, en Linux y en Mac. Pulsa **Super + .** en Linux
(o **⌃⌘.** en Mac) en cualquier aplicación, busca el emoji y pulsa Enter: se
escribe donde estabas.

- **Todos los emojis de Unicode 18.0** (septiembre de 2026), ordenados por
  categorías como en Windows: caras, personas, animales, comida, viajes,
  actividades, objetos, símbolos y banderas.
- **Búsqueda en tu idioma y en inglés.** Con Linux en español encuentras
  «corazón» y también «heart». Sin tildes también vale: «corazon». Los nombres
  vienen de Unicode CLDR 49 y hay 144 idiomas.
- **Usados recientemente**, guardados entre sesiones.
- **Tonos de piel**: el botón ✋ de abajo a la derecha cambia el tono de todas las
  personas y manos. Con clic derecho sobre un emoji eliges el tono solo para esa vez.
- **Pestaña de símbolos** (Ω): puntuación, moneda, letras latinas, geométricos,
  matemáticos, flechas y letras griegas y cirílicas.
- Solo enseña los emojis que tu fuente sabe dibujar: nunca verás cajas vacías.

Funciona en **KDE Plasma, GNOME, Cinnamon y XFCE**, en X11 y Wayland, en
Hyprland, Sway y niri, y en **macOS 12 o más reciente** (Apple Silicon e Intel).

| Emojis por categorías | Búsqueda en español | Símbolos |
| --- | --- | --- |
| ![Panel de emojis](docs/img/panel-emojis.png) | ![Búsqueda de «corazon»](docs/img/busqueda.png) | ![Pestaña de símbolos](docs/img/simbolos.png) |

## Instalación

Descarga el paquete de tu distribución desde la carpeta [`instalador/`](instalador).

**Debian, Ubuntu, Linux Mint, Pop!\_OS, Zorin**

```sh
sudo apt install ./emojis-linux_0.1.0_all.deb
```

**Fedora y Nobara**

```sh
sudo dnf install ./emojis-linux-0.1.0-1.noarch.rpm
```

**Arch Linux, CachyOS, EndeavourOS y Manjaro**

```sh
sudo pacman -U emojis-linux-0.1.0-1-any.pkg.tar.zst
```

o, desde el código: `cd packaging/arch && makepkg -si`.

Después abre **Emojis** desde el menú de aplicaciones una vez, o cierra sesión y
vuelve a entrar. Desde ese momento Super + . abre el panel.

**macOS**

1. Descarga el `.dmg` de tu Mac desde la versión
   [«Emojis para macOS»](https://github.com/anrennnn/EMON-Linux-MacOS/releases/tag/macos):
   `arm64` para Apple Silicon (M1, M2, M3, M4…) y `x86_64` para Mac con Intel.
2. Ábrelo y arrastra **Emojis** a **Aplicaciones**.
3. La primera vez, macOS dirá que no puede verificar la app (no está firmada
   por Apple). Ve a **Ajustes del Sistema → Privacidad y seguridad**, baja hasta
   «Emojis se bloqueó» y pulsa **Abrir igualmente**.
4. Para que el emoji se escriba solo en la otra app, activa Emojis en
   **Ajustes del Sistema → Privacidad y seguridad → Accesibilidad**. Sin ese
   permiso el emoji se copia y lo pegas con ⌘V.

Emojis no tiene icono en el Dock: queda esperando el atajo **⌃⌘.** (Control +
Comando + punto) o **⌃⌘;**, y se abre solo al iniciar sesión. ⌘. no se usa
porque en macOS significa «cancelar» en todas las apps.

## Uso

| Tecla | Qué hace |
| --- | --- |
| Super + . o Super + ; (Mac: ⌃⌘. o ⌃⌘;) | Abre el panel (si ya está abierto, lo cierra) |
| Escribir | Busca al instante |
| Flechas | Moverse entre los emojis |
| Enter o clic | Escribe el emoji y cierra el panel |
| Clic derecho | Elegir el tono de piel para ese emoji |
| Esc o clic fuera | Cierra el panel |

Desde la terminal:

```sh
emojis-linux abrir       # abrir el panel
emojis-linux simbolos    # abrir en la pestaña de símbolos
emojis-linux atajos      # volver a configurar Super+. en el escritorio
emojis-linux salir       # detener el proceso de fondo
emojis-linux version
```

## Cómo se escribe el emoji en la otra aplicación

Windows lo hace con su propio sistema de entrada de texto. En Linux depende de
la sesión:

| Sesión | Qué pasa | Necesita |
| --- | --- | --- |
| X11 (cualquier escritorio) | Se escribe directamente; el portapapeles no se toca | `xdotool` (se instala solo) |
| Wayland: Hyprland, Sway, niri, Wayfire | Se escribe directamente | `wtype` (se instala solo en Debian/Fedora) |
| Wayland: GNOME y KDE Plasma | Se copia y se pega solo | `ydotool` con su servicio activo |
| Wayland: GNOME y KDE Plasma sin ydotool | Se copia y aparece un aviso para pulsar Ctrl+V | — |
| macOS | Se escribe directamente | Permiso de Accesibilidad |
| macOS sin permiso | Se copia y aparece un aviso para pulsar ⌘V | — |

GNOME y KDE en Wayland no dejan, por diseño, que un programa teclee en la
ventana de otro. Para que pegue solo, activa ydotool:

```sh
sudo apt install ydotool        # o: sudo dnf install ydotool / sudo pacman -S ydotool
systemctl --user enable --now ydotool
```

## Atajos en cada escritorio

Al primer arranque, Emojis configura Super + . y Super + ; él solo:

- **GNOME**: dos atajos personalizados en Configuración → Teclado.
- **KDE Plasma**: el selector de emojis de KDE ya usa Meta + .; se le cambia a
  Meta + Ctrl + Alt + Mayús + Espacio y Emojis se queda con Meta + . y Meta + ;.
- **Cinnamon y XFCE**: atajos personalizados.
- **Hyprland, Sway y niri**: Emojis te dice qué línea añadir a tu configuración:

  ```
  bind = SUPER, period, exec, emojis-linux abrir          # Hyprland
  bindsym Mod4+period exec emojis-linux abrir             # Sway
  Mod+Period { spawn "emojis-linux" "abrir"; }            # niri
  ```

## Emojis nuevos y fuentes

Los dibujos los pone la fuente de emojis del sistema (Noto Color Emoji en
Linux, Apple Color Emoji en Mac). Emojis
incluye la lista completa de Unicode 18.0, pero solo enseña los que tu fuente
sabe dibujar, para que nunca veas cajas vacías. Los más nuevos (los 9 de
Unicode 18.0: cara agrietada, mariposa monarca, pepinillo, faro, meteorito,
goma de borrar, red, y pulgares hacia la izquierda y hacia la derecha)
aparecerán solos en cuanto tu distribución actualice la fuente. No hace falta
actualizar Emojis.

## Para desarrolladores

Python 3.10+ y PyQt6. En Linux el código se instala en `/usr/lib/emojis-linux` y
no en `site-packages`, así sigue funcionando cuando la distribución actualiza
Python. Lo propio de macOS está en `src/emojis_linux/macos.py` (atajo global con
Carbon, escritura con Quartz) y usa PyObjC.

```sh
PYTHONPATH=src python3 -m emojis_linux abrir   # probar sin instalar
./build-deb.sh                                  # dist/*.deb
./build-rpm.sh                                  # dist/*.rpm (necesita rpmbuild)
./build-arch.sh                                 # dist/*.pkg.tar.zst (necesita Docker)
macos/construir.sh                              # dist/*.dmg (en un Mac)
```

En cada cambio a `main`, GitHub Actions construye los `.dmg` en Macs reales
(Apple Silicon e Intel), comprueba que la app arranca y abre el panel, y los
publica en la versión «macos» junto con una captura de la prueba.

Los datos de `src/emojis_linux/datos` se generan con
`herramientas/generar_datos.py` a partir de `emoji-test.txt` de Unicode y de los
paquetes `cldr-annotations-full` y `cldr-annotations-derived-full`.

## Licencia

MIT. Los datos de emojis y nombres son de Unicode, Inc., con la licencia
[Unicode License v3](LICENSE-UNICODE).
