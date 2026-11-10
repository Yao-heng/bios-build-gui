"""PyQt6 GUI (main window).

The only component that depends on PyQt. It renders a fixed platform
label ("Platform: OvmfPkg"), a step indicator, the config editor, the
build log view, and the boot verification panel. It never calls EDK II
or QEMU directly; it calls only the Application Core (config, adapter,
runner, prereq, boot verify, settings).

Steps (five): Prerequisites -> Select platform -> Configure -> Build ->
Verify. The platform step is fixed in v1 (OvmfPkg only), so the
indicator moves from Prerequisites to Configure once the checks pass.

The build runs in a worker thread (a QThread owned by the GUI); the
``on_line`` callback forwards each line via the Qt signal
``log_line(str)`` so GUI updates happen on the GUI thread and the UI
stays responsive. Boot verification runs in a worker thread the same
way. Closing the GUI while a build or boot verify is running
terminates the subprocess first.
"""

from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bios_build_gui import boot_verify as boot_verify_mod
from bios_build_gui.adapters import ovmf
from bios_build_gui.build_runner import extract_error_block, run_build
from bios_build_gui.config import BuildConfig, load_config, save_config, validate
from bios_build_gui.prereq import check as check_prereqs
from bios_build_gui.settings import Settings, load_settings, save_settings

STEPS = ["Prerequisites", "Select platform", "Configure", "Build", "Verify"]
DEFAULT_CONFIG = BuildConfig()


class _Worker(QThread):
    """Run a build or a boot verify off the GUI thread."""

    log_line = pyqtSignal(str)
    build_finished = pyqtSignal(int)
    verify_finished = pyqtSignal(bool, str)

    def __init__(self, kind, **kwargs):
        super().__init__()
        self._kind = kind
        self._kwargs = kwargs
        self.cancel_event = threading.Event()

    def run(self):
        if self._kind == "build":
            rc = run_build(
                on_line=self.log_line.emit,
                cancel_event=self.cancel_event,
                **self._kwargs,
            )
            self.build_finished.emit(rc)
        else:
            booted, output = boot_verify_mod.verify_boot(
                cancel_event=self.cancel_event, **self._kwargs
            )
            self.verify_finished.emit(booted, output)


class MainWindow(QMainWindow):
    """The BIOS Build GUI main window."""

    def __init__(self, project_root=None):
        super().__init__()
        self._project_root = (
            Path(project_root)
            if project_root is not None
            else Path(__file__).resolve().parent.parent
        )
        self._settings = load_settings(self._project_root / "settings.json")
        self._config = BuildConfig()
        self._current_config_path: Path | None = None
        self._image_path: Path | None = None
        self._worker: _Worker | None = None
        self._log_path: Path | None = None
        self.setWindowTitle("BIOS Build GUI — OvmfPkg")
        self.resize(1000, 750)
        self._build_ui()
        self._apply_settings_to_core()
        self._set_step(0)
        self._run_prereq_check()
        self._populate_pcd_table({})

    # -- UI construction -------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        self._step_label = QLabel()
        layout.addWidget(self._step_label)

        self._platform_label = QLabel("Platform: OvmfPkg")
        layout.addWidget(self._platform_label)

        layout.addWidget(self._build_settings_group())
        layout.addWidget(self._build_prereq_group())
        layout.addWidget(self._build_config_group())
        layout.addWidget(self._build_build_group())
        layout.addWidget(self._build_log_group())
        layout.addWidget(self._build_verify_group())
        layout.addWidget(self._build_warnings_group())
        self._build_menu()

    def _build_settings_group(self):
        group = QGroupBox("Settings")
        row = QHBoxLayout(group)
        row.addWidget(QLabel("EDK II path:"))
        self._edk2_path_edit = QLineEdit(self._settings.edk2_path)
        row.addWidget(self._edk2_path_edit)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_browse_edk2_path)
        row.addWidget(browse)
        row.addWidget(QLabel("QEMU path (optional):"))
        self._qemu_path_edit = QLineEdit(self._settings.qemu_path)
        row.addWidget(self._qemu_path_edit)
        save = QPushButton("Save settings")
        save.clicked.connect(self._on_save_settings)
        row.addWidget(save)
        return group

    def _build_prereq_group(self):
        group = QGroupBox("Prerequisites")
        layout = QVBoxLayout(group)
        self._prereq_label = QLabel("Checking prerequisites...")
        self._prereq_label.setWordWrap(True)
        layout.addWidget(self._prereq_label)
        recheck = QPushButton("Re-check")
        recheck.clicked.connect(self._run_prereq_check)
        layout.addWidget(recheck)
        return group

    def _build_config_group(self):
        group = QGroupBox("Configuration")
        layout = QVBoxLayout(group)
        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Architecture:"))
        self._arch_combo = QComboBox()
        self._arch_combo.addItems(sorted(ovmf.SUPPORTED_ARCHITECTURES))
        form_row.addWidget(self._arch_combo)
        form_row.addWidget(QLabel("Build target:"))
        self._target_combo = QComboBox()
        self._target_combo.addItems(sorted(ovmf.SUPPORTED_BUILD_TARGETS))
        self._target_combo.setCurrentText("DEBUG")
        form_row.addWidget(self._target_combo)
        form_row.addWidget(QLabel("Toolchain:"))
        self._toolchain_combo = QComboBox()
        self._toolchain_combo.addItems(sorted(ovmf.SUPPORTED_TOOLCHAINS))
        form_row.addWidget(self._toolchain_combo)
        layout.addLayout(form_row)
        layout.addWidget(QLabel("PCDs (one row per offered PCD; edit the value):"))
        self._pcd_table = QTableWidget(0, 2)
        self._pcd_table.setHorizontalHeaderLabels(["PCD name", "Value"])
        self._pcd_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._pcd_table)
        add_pcd = QPushButton("Add PCD")
        add_pcd.clicked.connect(self._on_add_pcd_row)
        layout.addWidget(add_pcd)
        self._validation_label = QLabel()
        self._validation_label.setStyleSheet("color: red")
        self._validation_label.setWordWrap(True)
        layout.addWidget(self._validation_label)
        for combo in (self._arch_combo, self._target_combo, self._toolchain_combo):
            combo.currentTextChanged.connect(lambda _text: self._set_step(2))
        return group

    def _build_build_group(self):
        group = QGroupBox("Build")
        row = QHBoxLayout(group)
        self._build_button = QPushButton("Build")
        self._build_button.clicked.connect(self._on_build)
        row.addWidget(self._build_button)
        self._clean_build_button = QPushButton("Clean Build")
        self._clean_build_button.clicked.connect(self._on_clean_build)
        row.addWidget(self._clean_build_button)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._on_cancel)
        self._cancel_button.setEnabled(False)
        row.addWidget(self._cancel_button)
        self._build_status_label = QLabel("Not built yet.")
        self._build_status_label.setWordWrap(True)
        row.addWidget(self._build_status_label)
        return group

    def _build_log_group(self):
        group = QGroupBox("Build log")
        layout = QVBoxLayout(group)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        layout.addWidget(self._log_view)
        return group

    def _build_verify_group(self):
        group = QGroupBox("Boot verification")
        layout = QVBoxLayout(group)
        self._image_label = QLabel("No image built yet.")
        self._image_label.setWordWrap(True)
        layout.addWidget(self._image_label)
        self._qemu_command_label = QLabel("")
        self._qemu_command_label.setWordWrap(True)
        self._qemu_command_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._qemu_command_label)
        row = QHBoxLayout()
        self._verify_button = QPushButton("Boot Verify")
        self._verify_button.clicked.connect(self._on_boot_verify)
        self._verify_button.setEnabled(False)
        row.addWidget(self._verify_button)
        self._verdict_label = QLabel("")
        self._verdict_label.setWordWrap(True)
        row.addWidget(self._verdict_label)
        layout.addLayout(row)
        return group

    def _build_warnings_group(self):
        group = QGroupBox("Import warnings")
        layout = QVBoxLayout(group)
        self._warnings_view = QPlainTextEdit()
        self._warnings_view.setReadOnly(True)
        self._warnings_view.setMaximumBlockCount(200)
        layout.addWidget(self._warnings_view)
        return group

    def _build_menu(self):
        menu = self.menuBar().addMenu("File")
        open_action = menu.addAction("Open config...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_config)
        save_action = menu.addAction("Save config")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_config)
        save_as_action = menu.addAction("Save config as...")
        save_as_action.triggered.connect(self._on_save_config_as)
        import_action = menu.addAction("Import DSC/FDF...")
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._on_import)

    # -- settings / prerequisites -----------------------------------------

    def _apply_settings_to_core(self):
        ovmf.set_workspace(self._settings.edk2_path or None)
        boot_verify_mod.set_qemu_binary(self._settings.qemu_path or None)

    def _on_browse_edk2_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select EDK II tree")
        if path:
            self._edk2_path_edit.setText(path)
            self._on_save_settings()
            self._run_prereq_check()

    def _on_save_settings(self):
        self._settings = Settings(
            edk2_path=self._edk2_path_edit.text().strip(),
            qemu_path=self._qemu_path_edit.text().strip(),
        )
        save_settings(self._settings, self._project_root / "settings.json")
        self._apply_settings_to_core()
        self._run_prereq_check()

    def _run_prereq_check(self):
        results = check_prereqs(self._settings)
        lines = []
        all_ok = True
        for result in results:
            if result.status != "ok":
                all_ok = False
            detail = result.found_version or result.status
            lines.append(f"{result.name}: {result.status} ({detail})")
            if result.fix_hint:
                lines.append(f"  Fix: {result.fix_hint}")
        self._prereq_label.setText("\n".join(lines))
        self._build_button.setEnabled(all_ok and self._worker is None)
        self._clean_build_button.setEnabled(all_ok and self._worker is None)
        if all_ok:
            self._set_step(1)
        return all_ok

    # -- config editor -----------------------------------------------------

    def _offered_pcds(self):
        try:
            return sorted(ovmf.get_pcd_names())
        except (RuntimeError, FileNotFoundError):
            return []

    def _populate_pcd_table(self, pcds):
        names = sorted(set(self._offered_pcds()) | set(pcds))
        self._pcd_table.setRowCount(0)
        for name in names:
            self._add_pcd_row(name, pcds.get(name, ""), editable_name=False)

    def _add_pcd_row(self, name, value, editable_name):
        row = self._pcd_table.rowCount()
        self._pcd_table.insertRow(row)
        name_item = QTableWidgetItem(name)
        if not editable_name:
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        name_item.setData(Qt.ItemDataRole.UserRole, editable_name)
        self._pcd_table.setItem(row, 0, name_item)
        self._pcd_table.setItem(row, 1, QTableWidgetItem(value))

    def _on_add_pcd_row(self):
        self._add_pcd_row("", "", editable_name=True)
        self._set_step(2)

    def _collect_pcds_from_table(self):
        pcds = {}
        for row in range(self._pcd_table.rowCount()):
            name_item = self._pcd_table.item(row, 0)
            value_item = self._pcd_table.item(row, 1)
            if name_item is None or value_item is None:
                continue
            name = name_item.text().strip()
            value = value_item.text().strip()
            if not name or not value:
                continue
            pcds[name] = value
        return pcds

    def _collect_config_from_editor(self):
        return BuildConfig(
            schema_version="1",
            platform="OvmfPkg",
            architecture=self._arch_combo.currentText(),
            build_target=self._target_combo.currentText(),
            toolchain=self._toolchain_combo.currentText(),
            pcds=self._collect_pcds_from_table(),
        )

    def _apply_config_to_editor(self, config):
        self._arch_combo.setCurrentText(config.architecture)
        self._target_combo.setCurrentText(config.build_target)
        self._toolchain_combo.setCurrentText(config.toolchain)
        self._populate_pcd_table(config.pcds)
        self._config = config

    # -- file actions --------------------------------------------------------

    def _on_open_config(self):
        path, _selected = QFileDialog.getOpenFileName(
            self, "Open config", str(self._project_root / "configs"), "JSON (*.json)"
        )
        if not path:
            return
        try:
            config = load_config(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Open config", f"Could not load config:\n{exc}")
            return
        self._current_config_path = Path(path)
        self._apply_config_to_editor(config)
        self._set_step(2)

    def _on_save_config(self):
        config = self._collect_config_from_editor()
        if self._current_config_path is None:
            self._on_save_config_as()
            return
        save_config(config, self._current_config_path)
        self._config = config

    def _on_save_config_as(self):
        path, _selected = QFileDialog.getSaveFileName(
            self, "Save config as", str(self._project_root / "configs"), "JSON (*.json)"
        )
        if not path:
            return
        config = self._collect_config_from_editor()
        save_config(config, path)
        self._current_config_path = Path(path)
        self._config = config

    def _on_import(self):
        dsc_path, _selected = QFileDialog.getOpenFileName(self, "Import DSC", "", "DSC (*.dsc)")
        if not dsc_path:
            return
        fdf_guess = Path(dsc_path).with_suffix(".fdf")
        fdf_path = str(fdf_guess) if fdf_guess.is_file() else None
        if fdf_path is None:
            picked, _sel = QFileDialog.getOpenFileName(
                self, "Import FDF (optional)", "", "FDF (*.fdf)"
            )
            fdf_path = picked or None
        try:
            config, warnings = ovmf.import_config(dsc_path, fdf_path)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Import", f"Could not import:\n{exc}")
            return
        self._apply_config_to_editor(config)
        self._warnings_view.setPlainText(
            "\n".join(f"{w['name']}: {w['value']}" for w in warnings) or "No warnings."
        )
        self._set_step(2)

    # -- build ---------------------------------------------------------------

    def _on_clean_build(self):
        build_dir = None
        if self._settings.edk2_path:
            build_dir = Path(self._settings.edk2_path) / "Build" / "OvmfX64"
        if build_dir:
            shutil.rmtree(build_dir, ignore_errors=True)
        self._on_build()

    def _on_build(self):
        if self._worker is not None:
            return
        config = self._collect_config_from_editor()
        errors = validate(config, ovmf)
        if errors:
            self._validation_label.setText("\n".join(f"{e.field}: {e.message}" for e in errors))
            return
        self._validation_label.setText("")
        self._config = config
        configs_dir = self._project_root / "configs"
        save_config(config, configs_dir / "last.json")
        try:
            _dsc, _fdf, command, image_path = ovmf.generate(config)
        except (RuntimeError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "Generate", f"Could not generate DSC/FDF:\n{exc}")
            return
        self._image_path = image_path
        self._log_view.clear()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._log_path = self._project_root / "logs" / f"build-{timestamp}.log"
        self._set_step(3)
        self._build_status_label.setText("Building...")
        self._set_build_running(True)
        self._worker = _Worker(
            "build",
            command=command,
            workdir=self._settings.edk2_path,
            log_path=self._log_path,
        )
        self._worker.log_line.connect(self._log_view.appendPlainText)
        self._worker.build_finished.connect(self._on_build_finished)
        self._worker.start()

    def _on_build_finished(self, exit_code):
        self._worker = None
        self._set_build_running(False)
        if exit_code == 0 and self._image_path is not None:
            size = self._image_path.stat().st_size if self._image_path.exists() else 0
            timestamp = (
                datetime.fromtimestamp(self._image_path.stat().st_mtime).isoformat()
                if self._image_path.exists()
                else "unknown"
            )
            self._image_label.setText(
                f"Image: {self._image_path}\nSize: {size} bytes, built {timestamp}"
            )
            self._qemu_command_label.setText(
                "QEMU: qemu-system-x86_64 -machine q35 -m 1024 "
                f"-drive if=pflash,format=raw,unit=0,file={self._image_path},readonly=on "
                "-display none -serial stdio"
            )
            self._build_status_label.setText(f"Build succeeded. Log: {self._log_path}")
            self._verify_button.setEnabled(True)
            self._set_step(4)
        else:
            error_block = (
                extract_error_block(self._log_path)
                if self._log_path is not None and self._log_path.exists()
                else ""
            )
            self._build_status_label.setText(
                f"Build failed (exit code {exit_code}). Log: {self._log_path}\n{error_block}"
            )
            self._verify_button.setEnabled(False)

    def _set_build_running(self, running):
        self._build_button.setEnabled(not running)
        self._clean_build_button.setEnabled(not running)
        self._cancel_button.setEnabled(running)
        self._verify_button.setEnabled(False if running else self._verify_button.isEnabled())

    # -- boot verify -----------------------------------------------------------

    def _on_boot_verify(self):
        if self._worker is not None or self._image_path is None:
            return
        self._verdict_label.setText("Booting in QEMU...")
        self._set_build_running(True)
        self._worker = _Worker("verify", image_path=self._image_path, timeout=60)
        self._worker.verify_finished.connect(self._on_verify_finished)
        self._worker.start()

    def _on_verify_finished(self, booted, output):
        self._worker = None
        self._set_build_running(False)
        if booted:
            self._verdict_label.setText("Booted: UEFI shell prompt observed.")
        else:
            self._verdict_label.setText(
                "Not booted: shell prompt not observed within 60 s.\n" + output
            )

    # -- cancel / close ---------------------------------------------------------

    def _on_cancel(self):
        if self._worker is not None:
            self._worker.cancel_event.set()

    def _set_step(self, index):
        parts = []
        for i, name in enumerate(STEPS):
            if i == index:
                parts.append(f"<b>{i + 1}. {name}</b>")
            else:
                parts.append(f"{i + 1}. {name}")
        self._step_label.setText(" → ".join(parts))

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.cancel_event.set()
            self._worker.wait(5000)
        event.accept()
