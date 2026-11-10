#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firmador GUI - Interfaz gráfica para firma digital por lotes de documentos PDF.
Basado en JSignPdf a través de Flatpak.
"""

import sys
import os
import json
import subprocess
import shutil
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QFileDialog,
    QCheckBox, QSpinBox, QTextEdit, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox, QTabWidget,
    QComboBox, QSplitter, QStatusBar, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QFont

CONFIG_DIR = Path.home() / ".config" / "firmador-pdf"
CONFIG_FILE = CONFIG_DIR / "settings.json"


class CertVerifierThread(QThread):
    finished_check = pyqtSignal(bool, str)

    def __init__(self, cert_path, password):
        super().__init__()
        self.cert_path = cert_path
        self.password = password

    def run(self):
        cmd = [
            "flatpak", "run", "--filesystem=host", "io.github.intoolswetrust.JSignPdf",
            "--enable-stdin-passwords",
            "-kst", "PKCS12",
            "-ksf", self.cert_path,
            "-ksp", "-",
            "-lk", "-q"
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate(input=self.password)
            if proc.returncode == 0:
                aliases = [line.strip() for line in stdout.splitlines() if line.strip()]
                alias_str = ", ".join(aliases) if aliases else "Válido"
                self.finished_check.emit(True, f"Certificado verificado con éxito (Clave: {alias_str})")
            else:
                err_msg = stderr.strip() or stdout.strip()
                if "Failed PKCS12 integrity" in err_msg or "password" in err_msg.lower():
                    self.finished_check.emit(False, "Contraseña incorrecta o archivo de certificado corrupto.")
                else:
                    self.finished_check.emit(False, f"Error al leer certificado:\n{err_msg[:200]}")
        except Exception as e:
            self.finished_check.emit(False, f"Error ejecutando flatpak: {str(e)}")


class SignWorkerThread(QThread):
    file_started = pyqtSignal(int, str)
    file_finished = pyqtSignal(int, str, bool, str)
    batch_finished = pyqtSignal(int, int)
    log_message = pyqtSignal(str)

    def __init__(self, files, dest_dir, cert_path, password, visual_opts):
        super().__init__()
        self.files = files
        self.dest_dir = dest_dir
        self.cert_path = cert_path
        self.password = password
        self.visual_opts = visual_opts
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        success_count = 0
        fail_count = 0
        os.makedirs(self.dest_dir, exist_ok=True)

        for index, file_path in enumerate(self.files):
            if self.is_cancelled:
                self.log_message.emit(">>> Proceso cancelado por el usuario.")
                break

            filename = os.path.basename(file_path)
            self.file_started.emit(index, filename)
            self.log_message.emit(f"==> Iniciando firma de: {file_path}")

            cmd = [
                "flatpak", "run", "--filesystem=host", "io.github.intoolswetrust.JSignPdf",
                file_path,
                "-kst", "PKCS12",
                "-ksf", self.cert_path,
                "--enable-stdin-passwords",
                "-ksp", "-",
                "-d", self.dest_dir,
                "--overwrite"
            ]

            if self.visual_opts.get("visible", True):
                cmd.extend([
                    "-V",
                    "-pg", str(self.visual_opts.get("page", 1)),
                    "-llx", str(self.visual_opts.get("llx", 105)),
                    "-lly", str(self.visual_opts.get("lly", 80)),
                    "-urx", str(self.visual_opts.get("urx", 300)),
                    "-ury", str(self.visual_opts.get("ury", 113)),
                    "-fs", str(self.visual_opts.get("font_size", 7)),
                    "--l2-text", self.visual_opts.get("l2_text", "Firmado digitalmente por:\n${signer}\nFecha: ${timestamp}")
                ])

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = proc.communicate(input=self.password)

                if proc.returncode == 0:
                    success_count += 1
                    self.log_message.emit(f"[OK] Firmado con éxito: {filename}")
                    self.file_finished.emit(index, filename, True, "Firmado correctamente")
                else:
                    fail_count += 1
                    error_detail = stderr.strip() or stdout.strip() or f"Código de salida: {proc.returncode}"
                    self.log_message.emit(f"[ERROR] Error al firmar {filename}: {error_detail}")
                    self.file_finished.emit(index, filename, False, error_detail.splitlines()[-1] if error_detail else "Error")
            except Exception as e:
                fail_count += 1
                self.log_message.emit(f"[EXCEPCIÓN] {str(e)}")
                self.file_finished.emit(index, filename, False, str(e))

        self.batch_finished.emit(success_count, fail_count)


class FirmadorMainWindow(QMainWindow):
    PRESETS = {
        "Predeterminado (X: 105-300, Y: 80-113)": (105, 80, 300, 113),
        "Inferior Izquierda (X: 50-250, Y: 50-100)": (50, 50, 250, 100),
        "Inferior Derecha (X: -250 a -50, Y: 50-100)": (-250, 50, -50, 100),
        "Superior Derecha (X: -250 a -50, Y: -100 a -50)": (-250, -100, -50, -50),
        "Superior Izquierda (X: 50-250, Y: -100 a -50)": (50, -100, 250, -50),
        "Personalizado...": None
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Firmador Digital PDF - Por Lotes")
        self.setMinimumSize(850, 680)
        self.setWindowIcon(QIcon.fromTheme("document-sign"))

        self.files_to_sign = []
        self.worker = None
        self.verifier = None

        self.init_ui()
        self.load_settings()
        self.refresh_file_list()
        self.check_dependencies()

    def check_dependencies(self):
        if not shutil.which("flatpak"):
            self.statusBar().showMessage("Aviso: 'flatpak' no está instalado en el sistema.", 8000)
            return

        try:
            res = subprocess.run(
                ["flatpak", "info", "io.github.intoolswetrust.JSignPdf"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if res.returncode != 0:
                self.statusBar().showMessage(
                    "Aviso: JSignPdf no está instalado en Flatpak. Ejecuta: flatpak install io.github.intoolswetrust.JSignPdf",
                    10000
                )
        except Exception:
            pass

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        tabs = QTabWidget()
        main_layout.addWidget(tabs, stretch=1)

        # Tab 1: Proceso principal
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout(main_tab)
        main_tab_layout.setSpacing(8)

        # Grupo Directorios y Archivos
        files_group = QGroupBox("Archivos a Firmar")
        files_layout = QGridLayout(files_group)
        files_layout.setSpacing(6)

        files_layout.addWidget(QLabel("Carpeta de Origen:"), 0, 0)
        self.txt_source = QLineEdit()
        self.txt_source.textChanged.connect(self.on_source_path_changed)
        files_layout.addWidget(self.txt_source, 0, 1)

        btn_browse_source = QPushButton(QIcon.fromTheme("folder-open"), "Examinar...")
        btn_browse_source.clicked.connect(self.browse_source_dir)
        files_layout.addWidget(btn_browse_source, 0, 2)

        self.chk_recursive = QCheckBox("Buscar recursivamente en subcarpetas")
        self.chk_recursive.setChecked(True)
        self.chk_recursive.toggled.connect(self.refresh_file_list)
        files_layout.addWidget(self.chk_recursive, 1, 1)

        files_layout.addWidget(QLabel("Carpeta de Destino:"), 2, 0)
        self.txt_dest = QLineEdit()
        files_layout.addWidget(self.txt_dest, 2, 1)

        btn_browse_dest = QPushButton(QIcon.fromTheme("folder-open"), "Examinar...")
        btn_browse_dest.clicked.connect(self.browse_dest_dir)
        files_layout.addWidget(btn_browse_dest, 2, 2)

        main_tab_layout.addWidget(files_group)

        # Grupo Certificado
        cert_group = QGroupBox("Certificado Digital")
        cert_layout = QGridLayout(cert_group)
        cert_layout.setSpacing(6)

        cert_layout.addWidget(QLabel("Archivo Certificado (.p12 / .pfx):"), 0, 0)
        self.txt_cert = QLineEdit()
        cert_layout.addWidget(self.txt_cert, 0, 1)

        btn_browse_cert = QPushButton(QIcon.fromTheme("document-open"), "Examinar...")
        btn_browse_cert.clicked.connect(self.browse_cert_file)
        cert_layout.addWidget(btn_browse_cert, 0, 2)

        cert_layout.addWidget(QLabel("Contraseña del Certificado:"), 1, 0)
        pass_layout = QHBoxLayout()
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setPlaceholderText("Introduce la contraseña para desbloquear el certificado")
        pass_layout.addWidget(self.txt_pass)

        self.btn_toggle_pass = QPushButton("👁 Mostrar")
        self.btn_toggle_pass.setCheckable(True)
        self.btn_toggle_pass.toggled.connect(self.toggle_password_visibility)
        pass_layout.addWidget(self.btn_toggle_pass)

        self.btn_test_cert = QPushButton(QIcon.fromTheme("dialog-ok"), "Verificar Certificado")
        self.btn_test_cert.clicked.connect(self.verify_certificate)
        pass_layout.addWidget(self.btn_test_cert)

        cert_layout.addLayout(pass_layout, 1, 1, 1, 2)
        main_tab_layout.addWidget(cert_group)

        # Tabla de Archivos encontrados
        table_group = QGroupBox("Cola de Documentos")
        table_layout = QVBoxLayout(table_group)
        
        info_row = QHBoxLayout()
        self.lbl_file_count = QLabel("Documentos encontrados: 0")
        self.lbl_file_count.setStyleSheet("font-weight: bold;")
        info_row.addWidget(self.lbl_file_count)

        btn_refresh = QPushButton(QIcon.fromTheme("view-refresh"), "Actualizar lista")
        btn_refresh.clicked.connect(self.refresh_file_list)
        info_row.addWidget(btn_refresh)
        info_row.addStretch()

        table_layout.addLayout(info_row)

        self.tbl_files = QTableWidget(0, 3)
        self.tbl_files.setHorizontalHeaderLabels(["Nombre de Archivo", "Ruta Relativa / Completa", "Estado"])
        self.tbl_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_files.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_files.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_files.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_files.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.tbl_files)

        main_tab_layout.addWidget(table_group, stretch=1)
        tabs.addTab(main_tab, QIcon.fromTheme("application-pdf"), "Firma por Lotes")

        # Tab 2: Opciones de Estampa Visual
        visual_tab = QWidget()
        visual_tab_layout = QVBoxLayout(visual_tab)
        visual_group = QGroupBox("Configuración de Estampa Visual")
        vg_layout = QGridLayout(visual_group)

        self.chk_visible = QCheckBox("Añadir estampa visual de firma en el documento")
        self.chk_visible.setChecked(True)
        self.chk_visible.toggled.connect(self.on_visible_toggled)
        vg_layout.addWidget(self.chk_visible, 0, 0, 1, 3)

        vg_layout.addWidget(QLabel("Página de la estampa:"), 1, 0)
        self.cb_page_mode = QComboBox()
        self.cb_page_mode.addItems(["Primera página (1)", "Última página (-1)", "Página personalizada"])
        self.cb_page_mode.currentIndexChanged.connect(self.on_page_mode_changed)
        vg_layout.addWidget(self.cb_page_mode, 1, 1)

        self.spin_custom_page = QSpinBox()
        self.spin_custom_page.setRange(1, 9999)
        self.spin_custom_page.setValue(1)
        self.spin_custom_page.setEnabled(False)
        vg_layout.addWidget(self.spin_custom_page, 1, 2)

        vg_layout.addWidget(QLabel("Plantilla de Posición:"), 2, 0)
        self.cb_preset = QComboBox()
        for preset_name in self.PRESETS.keys():
            self.cb_preset.addItem(preset_name)
        self.cb_preset.currentIndexChanged.connect(self.on_preset_changed)
        vg_layout.addWidget(self.cb_preset, 2, 1, 1, 2)

        coords_box = QGroupBox("Coordenadas en Puntos (pt)")
        coords_layout = QGridLayout(coords_box)
        coords_layout.addWidget(QLabel("X inicial (LLX):"), 0, 0)
        self.spin_llx = QSpinBox()
        self.spin_llx.setRange(-2000, 2000)
        self.spin_llx.setValue(105)
        coords_layout.addWidget(self.spin_llx, 0, 1)

        coords_layout.addWidget(QLabel("Y inicial (LLY):"), 0, 2)
        self.spin_lly = QSpinBox()
        self.spin_lly.setRange(-2000, 2000)
        self.spin_lly.setValue(80)
        coords_layout.addWidget(self.spin_lly, 0, 3)

        coords_layout.addWidget(QLabel("X final (URX):"), 1, 0)
        self.spin_urx = QSpinBox()
        self.spin_urx.setRange(-2000, 2000)
        self.spin_urx.setValue(300)
        coords_layout.addWidget(self.spin_urx, 1, 1)

        coords_layout.addWidget(QLabel("Y final (URY):"), 1, 2)
        self.spin_ury = QSpinBox()
        self.spin_ury.setRange(-2000, 2000)
        self.spin_ury.setValue(113)
        coords_layout.addWidget(self.spin_ury, 1, 3)

        coords_layout.addWidget(QLabel("Tamaño de Fuente:"), 2, 0)
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(4, 30)
        self.spin_font_size.setValue(7)
        coords_layout.addWidget(self.spin_font_size, 2, 1)

        vg_layout.addWidget(coords_box, 3, 0, 1, 3)

        vg_layout.addWidget(QLabel("Texto de la Firma:"), 4, 0)
        self.txt_l2_text = QTextEdit()
        self.txt_l2_text.setMaximumHeight(90)
        self.txt_l2_text.setText("Firmado digitalmente por:\n${signer}\nFecha: ${timestamp}")
        vg_layout.addWidget(self.txt_l2_text, 4, 1, 1, 2)

        lbl_vars = QLabel("<small>Variables disponibles: <b>${signer}</b> (firmante), <b>${timestamp}</b> (fecha/hora), <b>${reason}</b>, <b>${location}</b></small>")
        lbl_vars.setTextFormat(Qt.RichText)
        vg_layout.addWidget(lbl_vars, 5, 1, 1, 2)

        visual_tab_layout.addWidget(visual_group)
        visual_tab_layout.addStretch()
        tabs.addTab(visual_tab, QIcon.fromTheme("document-edit"), "Opciones de Estampa")

        # Tab 3: Registro de Consola
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.txt_log)
        btn_clear_log = QPushButton(QIcon.fromTheme("edit-clear"), "Limpiar Registro")
        btn_clear_log.clicked.connect(self.txt_log.clear)
        log_layout.addWidget(btn_clear_log, alignment=Qt.AlignRight)
        tabs.addTab(log_tab, QIcon.fromTheme("utilities-terminal"), "Registro de Actividad")

        # Panel Inferior de Acción y Progreso
        action_panel = QFrame()
        action_layout = QVBoxLayout(action_panel)
        action_layout.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m completados)")
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.chk_open_dest = QCheckBox("Abrir carpeta de destino al finalizar")
        self.chk_open_dest.setChecked(True)
        btn_row.addWidget(self.chk_open_dest)

        btn_row.addStretch()

        self.btn_cancel = QPushButton(QIcon.fromTheme("process-stop"), "Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_signing)
        btn_row.addWidget(self.btn_cancel)

        self.btn_sign = QPushButton(QIcon.fromTheme("document-sign"), "Firmar Documentos")
        self.btn_sign.setStyleSheet("QPushButton { font-weight: bold; padding: 8px 18px; }")
        self.btn_sign.clicked.connect(self.start_signing)
        btn_row.addWidget(self.btn_sign)

        action_layout.addLayout(btn_row)
        main_layout.addWidget(action_panel)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo para firmar.")

    def toggle_password_visibility(self, checked):
        if checked:
            self.txt_pass.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_pass.setText("🔒 Ocultar")
        else:
            self.txt_pass.setEchoMode(QLineEdit.Password)
            self.btn_toggle_pass.setText("👁 Mostrar")

    def on_source_path_changed(self):
        self.refresh_file_list()

    def browse_source_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Origen", self.txt_source.text() or str(Path.home()))
        if d:
            self.txt_source.setText(d)

    def browse_dest_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Destino", self.txt_dest.text() or str(Path.home()))
        if d:
            self.txt_dest.setText(d)

    def browse_cert_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Certificado Digital",
            self.txt_cert.text() or str(Path.home()),
            "Certificados PKCS#12 (*.p12 *.pfx);;Todos los archivos (*)"
        )
        if f:
            self.txt_cert.setText(f)

    def on_page_mode_changed(self, idx):
        self.spin_custom_page.setEnabled(idx == 2)

    def on_preset_changed(self, idx):
        name = self.cb_preset.currentText()
        preset = self.PRESETS.get(name)
        if preset is not None:
            llx, lly, urx, ury = preset
            self.spin_llx.setValue(llx)
            self.spin_lly.setValue(lly)
            self.spin_urx.setValue(urx)
            self.spin_ury.setValue(ury)

    def on_visible_toggled(self, checked):
        self.cb_page_mode.setEnabled(checked)
        self.spin_custom_page.setEnabled(checked and self.cb_page_mode.currentIndex() == 2)
        self.cb_preset.setEnabled(checked)
        self.spin_llx.setEnabled(checked)
        self.spin_lly.setEnabled(checked)
        self.spin_urx.setEnabled(checked)
        self.spin_ury.setEnabled(checked)
        self.spin_font_size.setEnabled(checked)
        self.txt_l2_text.setEnabled(checked)

    def refresh_file_list(self):
        source_dir = self.txt_source.text().strip()
        self.files_to_sign = []
        self.tbl_files.setRowCount(0)

        if not source_dir or not os.path.isdir(source_dir):
            self.lbl_file_count.setText("Documentos encontrados: 0 (Carpeta no válida)")
            return

        is_recursive = self.chk_recursive.isChecked()
        p = Path(source_dir)

        pattern = "**/*.pdf" if is_recursive else "*.pdf"
        try:
            matched_files = sorted(
                [f for f in p.glob(pattern) if f.is_file() and not f.name.startswith(".")],
                key=lambda x: str(x).lower()
            )
            self.files_to_sign = [str(f) for f in matched_files]
            self.tbl_files.setRowCount(len(self.files_to_sign))

            for row, f_path in enumerate(self.files_to_sign):
                fname = os.path.basename(f_path)
                rel_path = os.path.relpath(f_path, source_dir)

                name_item = QTableWidgetItem(fname)
                path_item = QTableWidgetItem(rel_path)
                status_item = QTableWidgetItem("Pendiente")
                status_item.setForeground(QColor(100, 100, 100))

                self.tbl_files.setItem(row, 0, name_item)
                self.tbl_files.setItem(row, 1, path_item)
                self.tbl_files.setItem(row, 2, status_item)

            self.lbl_file_count.setText(f"Documentos encontrados: {len(self.files_to_sign)}")
            self.status_bar.showMessage(f"Se encontraron {len(self.files_to_sign)} archivos PDF en la carpeta origen.")
        except Exception as e:
            self.lbl_file_count.setText(f"Error al listar: {str(e)}")

    def verify_certificate(self):
        cert = self.txt_cert.text().strip()
        password = self.txt_pass.text()

        if not cert or not os.path.isfile(cert):
            QMessageBox.warning(self, "Aviso", "Por favor, indica un archivo de certificado válido (.p12 o .pfx).")
            return

        if not password:
            QMessageBox.warning(self, "Aviso", "Introduce la contraseña del certificado para verificarlo.")
            return

        self.btn_test_cert.setEnabled(False)
        self.status_bar.showMessage("Verificando certificado...")
        self.verifier = CertVerifierThread(cert, password)
        self.verifier.finished_check.connect(self.on_verify_finished)
        self.verifier.start()

    def on_verify_finished(self, ok, message):
        self.btn_test_cert.setEnabled(True)
        if ok:
            self.status_bar.showMessage(message, 6000)
            QMessageBox.information(self, "Certificado Válido", message)
        else:
            self.status_bar.showMessage("Error en certificado.", 6000)
            QMessageBox.critical(self, "Error en Certificado", message)

    def start_signing(self):
        if not self.files_to_sign:
            QMessageBox.warning(self, "Sin archivos", "No hay archivos PDF para firmar en la carpeta origen.")
            return

        cert = self.txt_cert.text().strip()
        dest = self.txt_dest.text().strip()
        password = self.txt_pass.text()

        if not cert or not os.path.isfile(cert):
            QMessageBox.warning(self, "Certificado no encontrado", "Debes seleccionar un archivo de certificado válido.")
            return

        if not dest:
            QMessageBox.warning(self, "Destino no especificado", "Debes seleccionar una carpeta de destino.")
            return

        if not password:
            QMessageBox.warning(self, "Contraseña requerida", "Por favor, introduce la contraseña del certificado.")
            return

        self.save_settings()

        # Preparar UI para ejecución
        self.btn_sign.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.files_to_sign))
        self.progress_bar.setValue(0)

        # Opciones visuales
        page_mode = self.cb_page_mode.currentIndex()
        if page_mode == 0:
            page_val = 1
        elif page_mode == 1:
            page_val = -1
        else:
            page_val = self.spin_custom_page.value()

        visual_opts = {
            "visible": self.chk_visible.isChecked(),
            "page": page_val,
            "llx": self.spin_llx.value(),
            "lly": self.spin_lly.value(),
            "urx": self.spin_urx.value(),
            "ury": self.spin_ury.value(),
            "font_size": self.spin_font_size.value(),
            "l2_text": self.txt_l2_text.toPlainText()
        }

        # Resetear estado de la tabla
        for r in range(self.tbl_files.rowCount()):
            item = self.tbl_files.item(r, 2)
            if item:
                item.setText("En espera")
                item.setForeground(QColor(120, 120, 120))

        self.worker = SignWorkerThread(self.files_to_sign, dest, cert, password, visual_opts)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_finished.connect(self.on_file_finished)
        self.worker.batch_finished.connect(self.on_batch_finished)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.start()

    def cancel_signing(self):
        if self.worker and self.worker.isRunning():
            self.btn_cancel.setEnabled(False)
            self.status_bar.showMessage("Cancelando proceso...")
            self.worker.cancel()

    def on_file_started(self, index, filename):
        item = self.tbl_files.item(index, 2)
        if item:
            item.setText("Firmando...")
            item.setForeground(QColor(0, 120, 215))
        self.tbl_files.scrollToItem(item)
        self.status_bar.showMessage(f"Firmando documento {index + 1} de {len(self.files_to_sign)}: {filename}")

    def on_file_finished(self, index, filename, ok, msg):
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        item = self.tbl_files.item(index, 2)
        if item:
            if ok:
                item.setText("✓ Firmado")
                item.setForeground(QColor(30, 150, 40))
            else:
                item.setText("✗ Error")
                item.setToolTip(msg)
                item.setForeground(QColor(200, 30, 30))

    def on_batch_finished(self, success_count, fail_count):
        self.btn_sign.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        total = success_count + fail_count

        msg = f"Proceso finalizado.\n\nFirmados con éxito: {success_count}\nErrores: {fail_count}"
        self.status_bar.showMessage(f"Finalizado: {success_count} correctos, {fail_count} errores.")

        if fail_count == 0:
            QMessageBox.information(self, "Firma completada", msg)
        else:
            QMessageBox.warning(self, "Firma con advertencias", msg + "\nConsulta la pestaña 'Registro de Actividad' para más detalles.")

        if self.chk_open_dest.isChecked():
            dest = self.txt_dest.text().strip()
            if os.path.isdir(dest):
                subprocess.Popen(["xdg-open", dest])

    def on_log_message(self, message):
        self.txt_log.append(message)

    def load_settings(self):
        defaults = {
            "source_dir": str(Path.home() / "Documentos"),
            "dest_dir": str(Path.home() / "Documentos"),
            "cert_path": "",
            "recursive": True,
            "visible": True,
            "page_mode": 0,
            "custom_page": 1,
            "preset_idx": 0,
            "llx": 105,
            "lly": 80,
            "urx": 300,
            "ury": 113,
            "font_size": 7,
            "l2_text": "Firmado digitalmente por:\n${signer}\nFecha: ${timestamp}",
            "open_dest": True
        }
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception:
                pass

        self.txt_source.setText(defaults["source_dir"])
        self.txt_dest.setText(defaults["dest_dir"])
        self.txt_cert.setText(defaults["cert_path"])
        self.chk_recursive.setChecked(defaults["recursive"])
        self.chk_visible.setChecked(defaults["visible"])
        self.cb_page_mode.setCurrentIndex(defaults["page_mode"])
        self.spin_custom_page.setValue(defaults["custom_page"])
        self.cb_preset.setCurrentIndex(defaults["preset_idx"])
        self.spin_llx.setValue(defaults["llx"])
        self.spin_lly.setValue(defaults["lly"])
        self.spin_urx.setValue(defaults["urx"])
        self.spin_ury.setValue(defaults["ury"])
        self.spin_font_size.setValue(defaults["font_size"])
        self.txt_l2_text.setPlainText(defaults["l2_text"])
        self.chk_open_dest.setChecked(defaults["open_dest"])

    def save_settings(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "source_dir": self.txt_source.text().strip(),
            "dest_dir": self.txt_dest.text().strip(),
            "cert_path": self.txt_cert.text().strip(),
            "recursive": self.chk_recursive.isChecked(),
            "visible": self.chk_visible.isChecked(),
            "page_mode": self.cb_page_mode.currentIndex(),
            "custom_page": self.spin_custom_page.value(),
            "preset_idx": self.cb_preset.currentIndex(),
            "llx": self.spin_llx.value(),
            "lly": self.spin_lly.value(),
            "urx": self.spin_urx.value(),
            "ury": self.spin_ury.value(),
            "font_size": self.spin_font_size.value(),
            "l2_text": self.txt_l2_text.toPlainText(),
            "open_dest": self.chk_open_dest.isChecked()
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def closeEvent(self, event):
        self.save_settings()
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Confirmar salida",
                "Hay un proceso de firma en marcha. ¿Deseas cancelarlo y salir?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                self.worker.wait(2000)
                event.accept()
            else:
                event.ignore()
                return
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Firmador PDF")
    app.setStyle("Fusion")
    window = FirmadorMainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
