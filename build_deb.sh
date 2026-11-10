#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Script para empaquetar Firmador PDF GUI en formato Debian (.deb)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="firmador-gui"
PKG_VERSION="1.1.1"
PKG_ARCH="all"
OUTPUT_DIR="${SCRIPT_DIR}/dist"
DEB_FILE="${OUTPUT_DIR}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

echo "==> Iniciando construcción del paquete .deb para ${PKG_NAME} v${PKG_VERSION}..."

# Directorio temporal de empaquetado
BUILD_DIR="$(mktemp -d -t ${PKG_NAME}-deb-XXXXXX)"
trap 'rm -rf "${BUILD_DIR}"' EXIT

# Crear estructura estándar del sistema de archivos Debian
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/share/applications"

# Copiar ejecutable
echo "==> Copiando ejecutable..."
cp "${SCRIPT_DIR}/firmador-gui.py" "${BUILD_DIR}/usr/bin/firmador-gui"
chmod 755 "${BUILD_DIR}/usr/bin/firmador-gui"

# Copiar lanzador de escritorio
echo "==> Copiando archivo .desktop..."
cp "${SCRIPT_DIR}/firmador-gui.desktop" "${BUILD_DIR}/usr/share/applications/firmador-gui.desktop"
chmod 644 "${BUILD_DIR}/usr/share/applications/firmador-gui.desktop"

# Generar archivo DEBIAN/control
echo "==> Generando metadatos (DEBIAN/control)..."
cat <<EOF > "${BUILD_DIR}/DEBIAN/control"
Package: ${PKG_NAME}
Version: ${PKG_VERSION}
Section: utils
Priority: optional
Architecture: ${PKG_ARCH}
Depends: python3, python3-pyqt5, flatpak, poppler-utils
Maintainer: Firmador PDF Developers
Description: Interfaz gráfica para firma digital por lotes de documentos PDF
 Firmador GUI facilita la firma digital masiva de archivos PDF
 mediante certificados digitales PKCS#12 (.p12/.pfx) y JSignPdf.
EOF

# Generar script post-instalación con auto-instalación de JSignPdf
echo "==> Generando DEBIAN/postinst..."
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/bash
set -e

# Configuración automática de Flatpak y JSignPdf a nivel de sistema
if command -v flatpak >/dev/null 2>&1; then
    echo "==> Verificando repositorio Flathub..."
    flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true

    if ! flatpak info io.github.intoolswetrust.JSignPdf >/dev/null 2>&1; then
        echo "==> Descargando e instalando JSignPdf automáticamente desde Flathub..."
        if flatpak install -y --noninteractive flathub io.github.intoolswetrust.JSignPdf 2>/dev/null; then
            echo "==> JSignPdf instalado correctamente a nivel de sistema."
        else
            echo ""
            echo "================================================================="
            echo " [AVISO] No se pudo descargar JSignPdf de forma automática"
            echo " (posiblemente por falta de conexión a internet temporal)."
            echo " Puedes completar la instalación ejecutando:"
            echo "   flatpak install -y flathub io.github.intoolswetrust.JSignPdf"
            echo "================================================================="
            echo ""
        fi
    fi

    echo "==> Asegurando permisos de acceso al sistema de archivos para JSignPdf..."
    flatpak override --system --filesystem=host io.github.intoolswetrust.JSignPdf 2>/dev/null || true
fi

exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

# Construir paquete .deb
mkdir -p "${OUTPUT_DIR}"
echo "==> Empaquetando con dpkg-deb..."
dpkg-deb --build --root-owner-group "${BUILD_DIR}" "${DEB_FILE}"

echo ""
echo "================================================================="
echo "  ¡Paquete generado con éxito!"
echo "  Archivo: ${DEB_FILE}"
echo "  Tamaño:  $(du -h "${DEB_FILE}" | cut -f1)"
echo ""
echo "  Para probar la instalación localmente:"
echo "    sudo apt install ${DEB_FILE}"
echo "================================================================="
