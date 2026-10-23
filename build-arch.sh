#!/bin/sh
# Construye dist/emon-<versión>-1-any.pkg.tar.zst con makepkg dentro de un
# contenedor de Arch (hace falta Docker). Usa los archivos actuales del repositorio.
set -eu
cd "$(dirname "$0")"
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' src/emon/config.py)
COMMIT=local
WORK=$(pwd)/build/arch
rm -rf "$WORK"
mkdir -p "$WORK" dist
tar --transform "s,^,Emon-Linux-MacOS-$COMMIT/," -czf "$WORK/emon-$VERSION.tar.gz" \
    Makefile LICENSE LICENSE-UNICODE README.md src data
sed -e "s/^_commit=.*/_commit=$COMMIT/" -e "s/^sha256sums=.*/sha256sums=(SKIP)/" -e "s/^pkgver=.*/pkgver=$VERSION/" \
    packaging/arch/PKGBUILD > "$WORK/PKGBUILD"
cp packaging/arch/emon.install "$WORK/"
docker run --rm -v "$WORK:/build" archlinux:base-devel sh -c '
    useradd -m builder && chown -R builder /build &&
    su builder -c "cd /build && makepkg --nodeps --noconfirm"'
cp "$WORK"/emon-*.pkg.tar.zst dist/
