# Firmador Digital PDF (GUI) 📄✍️

Interfaz gráfica moderna en Python (PyQt5) para la **firma digital por lotes de documentos PDF** en Linux, utilizando [JSignPdf](http://jsignpdf.sourceforge.net/) a través de **Flatpak**.

Diseñado para facilitar la firma masiva de documentación oficial con certificados digitales software (`.p12` / `.pfx`), como los emitidos por la FNMT, DNIe, CATCert/idCAT, etc.

---

## ✨ Características

- **Firma por lotes masiva**: Procesa directorios enteros de PDFs en segundos, con opción de búsqueda recursiva en subcarpetas.
- **Verificación rápida de certificado**: Permite comprobar si el archivo `.p12`/`.pfx` y la contraseña son válidos antes de iniciar el proceso.
- **Estampa visual personalizable**:
  - Firma visible o invisible.
  - Selección de página (primera página, última página o página específica).
  - Presets de posición (inferior derecha, inferior izquierda, etc.) o coordenadas manuales exactas.
  - Texto de firma configurable con variables dinámicas (`${signer}`, `${timestamp}`).
- **Monitoreo en tiempo real**: Tabla interactiva con estado individual por documento (*En cola*, *Firmando*, *Completado*, *Error*) y barra de progreso general.
- **Cancelación segura**: Posibilidad de detener el proceso de firma en cualquier momento sin corromper el documento en curso.
- **Persistencia de preferencias**: Recuerda automáticamente las últimas rutas y opciones de estampa utilizadas (`~/.config/firmador-pdf/settings.json`).

---

## 📋 Requisitos Previos

1. **Python 3** (>= 3.8) con soporte para **PyQt5**.
2. **Flatpak** con la aplicación **JSignPdf** instalada:

```bash
flatpak install flathub io.github.intoolswetrust.JSignPdf
```

---

## 🚀 Instalación y Uso

### Opción A: Paquete Debian / Ubuntu (.deb) - *Recomendado*

Si usas Ubuntu, Debian, Linux Mint o derivadas, puedes generar e instalar directamente el paquete `.deb`:

```bash
# Construir el paquete
./build_deb.sh

# Instalarlo (resuelve dependencias automáticamente)
sudo apt install ./dist/firmador-gui_1.0.0_all.deb
```
*(También podrás descargar el archivo `.deb` directamente desde la pestaña de **Releases** de este repositorio).*

---

### Opción B: Ejecución directa desde el código fuente

---

## 🖥️ Integración con el sistema (Opcional)

Si deseas poder lanzar la aplicación desde el menú de aplicaciones de tu escritorio o desde cualquier terminal:

```bash
# Dar permisos de ejecución
chmod +x firmador-gui.py

# Crear enlace en el directorio de ejecutables de usuario
mkdir -p ~/.local/bin
ln -sf "$(pwd)/firmador-gui.py" ~/.local/bin/firmador-gui

# Copiar el acceso directo al menú de aplicaciones
mkdir -p ~/.local/share/applications
cp firmador-gui.desktop ~/.local/share/applications/
```

---

## 🔒 Privacidad y Seguridad

- Las contraseñas introducidas **no se guardan** en disco ni en archivos de configuración.
- La comunicación de la contraseña hacia el proceso de firma se realiza de manera segura mediante tubería estándar (`stdin`), impidiendo que aparezca en el listado de procesos del sistema (`ps`, `top`).

---

## 📄 Licencia

Distribuido bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más información.
