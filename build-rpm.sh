#!/bin/sh
# Construye dist/emon-<versión>-1.noarch.rpm (Fedora, Nobara).
# Necesita rpmbuild (en Fedora: dnf install rpm-build; en Debian/Ubuntu: apt install rpm).
set -eu
cd "$(dirname "$0")"
# Fuera de Fedora, rpm no conoce los paquetes del sistema: no se comprueba BuildRequires.
NODEPS=""
[ -e /etc/fedora-release ] || NODEPS="--nodeps"
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' src/emon/config.py)
TOP=$(pwd)/build/rpm
rm -rf "$TOP"
mkdir -p "$TOP/SOURCES" "$TOP/SPECS" dist

# Tarball con los archivos actuales (no hace falta que estén confirmados en git).
tar --transform "s,^,emon-$VERSION/," -czf "$TOP/SOURCES/emon-$VERSION.tar.gz" \
    Makefile LICENSE LICENSE-UNICODE README.md src data
sed "s/@VERSION@/$VERSION/" packaging/fedora/emon.spec > "$TOP/SPECS/emon.spec"
rpmbuild $NODEPS --define "_topdir $TOP" -bb "$TOP/SPECS/emon.spec"
cp "$TOP"/RPMS/noarch/*.rpm dist/
