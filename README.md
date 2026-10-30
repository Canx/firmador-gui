# Firmador PDF GUI 📄✍️

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3" />
  <img src="https://img.shields.io/badge/GUI-PyQt5-41CD52?style=flat&logo=qt&logoColor=white" alt="PyQt5" />
  <img src="https://img.shields.io/badge/Backend-JSignPdf%20(Flatpak)-blue?style=flat" alt="JSignPdf" />
  <img src="https://img.shields.io/badge/Platform-Linux-FCC624?style=flat&logo=linux&logoColor=black" alt="Linux" />
  <img src="https://img.shields.io/badge/Package-.deb-A81D33?style=flat&logo=debian&logoColor=white" alt="Debian Package" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" />
</p>

**Firmador PDF GUI** es una aplicación gráfica de escritorio para Linux diseñada para la **firma digital masiva y por lotes de documentos PDF** mediante certificados software en formato PKCS#12 (`.p12` o `.pfx`).

Se apoya en el motor criptográfico de **[JSignPdf](http://jsignpdf.sourceforge.net/)** distribuido a través de **Flatpak**, garantizando un entorno aislado, robusto y compatible con certificados emitidos por la **FNMT**, **DNIe**, **CATCert / idCAT**, **ACCV**, **Camerfirma**, etc.

---

## ✨ Características Principales

- 📂 **Firma Masiva por Lotes:** Procesa cientos de documentos PDF de una carpeta con un solo clic, con soporte opcional para búsqueda recursiva en subcarpetas.
- 🔑 **Verificación Previa de Certificado:** Comprueba si la contraseña y el archivo de certificado son correctos antes de lanzar la firma, evitando fallos a mitad de proceso.
- 🎨 **Estampa Visual Totalmente Configurable:**
  - Firma visible o invisible.
  - Selección de página: primera página, última página o página específica.
  - Presets de posición (inferior derecha, inferior izquierda, etc.) o coordenadas milimétricas exactas.
  - Texto dinámico parametrizable con variables como `${signer}` y `${timestamp}`.
- 📊 **Monitorización en Tiempo Real:** Tabla interactiva que detalla el progreso individual (*En cola*, *Firmando...*, *Completado*, *Error*) junto a una barra de progreso general.
- 🛑 **Cancelación Segura:** Permite detener el proceso en cualquier momento sin riesgo de corromper el documento que se esté procesando.
- 💾 **Memoria de Configuración:** Recuerda automáticamente las rutas y las preferencias de firma utilizadas entre sesiones (`~/.config/firmador-pdf/settings.json`).

---

## 🚀 Instalación

### Opción 1: Mediante Paquete Debian / Ubuntu (`.deb`) — *Recomendado*

El paquete `.deb` configura automáticamente el acceso directo en el sistema, las dependencias de Python y el entorno de Flatpak con JSignPdf.

1. **Descarga el paquete** desde la sección de [**Releases**](../../releases) o genéralo tú mismo:
   ```bash
   ./build_deb.sh
   ```
2. **Instálalo con `apt`**:
   ```bash
   sudo apt install ./dist/firmador-gui_1.0.0_all.deb
   ```
3. ¡Listo! Ya puedes abrir **Firmador PDF** desde el menú de aplicaciones de tu escritorio o ejecutando `firmador-gui` en tu terminal.

---

### Opción 2: Ejecución directa desde el código fuente

Si prefieres ejecutarlo sin instalar el paquete `.deb`:

#### 1. Requisitos previos
* **Python 3** con PyQt5:
  ```bash
  sudo apt install python3-pyqt5
  # O bien con pip: pip install -r requirements.txt
  ```
* **Flatpak** con JSignPdf:
  ```bash
  flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
  flatpak install flathub io.github.intoolswetrust.JSignPdf
  ```

#### 2. Ejecutar la aplicación
```bash
git clone https://github.com/Canx/firmador-gui.git
cd firmador-gui
python3 firmador-gui.py
```

---

## 📖 Modo de Uso

1. **Carpeta Origen:** Selecciona el directorio que contiene los archivos PDF a firmar. Marca *«Buscar recursivamente en subcarpetas»* si tienes PDFs organizados en carpetas internas.
2. **Carpeta Destino:** Elige dónde se guardarán los documentos firmados.
3. **Certificado:** Selecciona tu archivo de certificado `.p12` o `.pfx` e introduce tu contraseña. Puedes pulsar el botón **«Verificar Certificado»** para comprobar su validez.
4. **Opciones de Estampa:** (Opcional) En la segunda pestaña puedes definir si la firma tendrá representación visual, en qué página aparecerá y la posición del recuadro.
5. **Firmar:** Pulsa el botón verde **«Firmar Documentos»**.

---

## 🔒 Privacidad y Seguridad

- **Tus credenciales no se almacenan:** La contraseña de tu certificado nunca se guarda en el disco duro ni en archivos de configuración.
- **Paso seguro por tubería:** La contraseña se transmite al proceso de firma mediante entrada estándar protegida (`stdin`), evitando que sea visible en herramientas de inspección de procesos del sistema como `ps aux` o `top`.

---

## 🛠️ Desarrollo y Empaquetado

Para generar un nuevo instalador `.deb` tras realizar cambios en el código:

```bash
chmod +x build_deb.sh
./build_deb.sh
```

El instalador resultante se generará en la carpeta `dist/firmador-gui_1.0.0_all.deb`.

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia **MIT**. Para más detalles, consulta el archivo [LICENSE](LICENSE).
