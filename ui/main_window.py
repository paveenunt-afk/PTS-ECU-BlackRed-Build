from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QSettings, QThread, QTimer, Qt
from PyQt5.QtWidgets import (
    QAction, QDockWidget, QFileDialog, QMainWindow, QMessageBox, QTabWidget
)

from core.bin_engine import BinImage
from core.map_model import CalibrationMap
from core.session_state import SessionState
from core.xdf_parser import parse_xdf
from hardware.ecu_profiles import (
    builtin_profiles, generic_kline_read_only_profile, mock_demo_profile,
    validate_flash_preconditions,
)
from hardware.mock_interface import MockInterface
from hardware.serial_interface import SerialInterface
from ui.dialogs import confirm_flash, show_error, show_info
from ui.logger_page import LoggerPage
from ui.serial_console import SerialConsole
from ui.tuning_page import TuningPage
from ui.welcome_page import WelcomePage
from workers.flash_worker import FlashWorker
from workers.logger_worker import LoggerWorker
from voice_manager import list_voices, speak


class MainWindow(QMainWindow):
    def __init__(self, parent=None, *, auto_start_mock: bool = True):
        super().__init__(parent)
        self.setWindowTitle("PTS ECU Tuning, Data Logger & Software Flash")
        self.resize(1400, 900)
        self.setMinimumSize(1050, 680)

        self.state = SessionState()
        self.settings = QSettings("PTS", "ECUTuningSuite")
        self.state.last_folder = self.settings.value("lastFolder", "", type=str)
        self.profiles = {p.profile_id: p for p in builtin_profiles()}
        self.backend = MockInterface(seed=7)
        self.state.backend_name = "Mock"
        self.state.ecu_profile = mock_demo_profile()

        self.logger_thread: QThread | None = None
        self.logger_worker: LoggerWorker | None = None
        self.flash_thread: QThread | None = None
        self.flash_worker: FlashWorker | None = None

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)
        self.welcome = WelcomePage()
        self.tuning = TuningPage()
        self.logger = LoggerPage()
        self.tabs.addTab(self.welcome, "Welcome")
        self.tabs.addTab(self.tuning, "Tuning Grid")
        self.tabs.addTab(self.logger, "Datalog Graph")

        self.serial_console = SerialConsole()
        self.serial_dock = QDockWidget("Serial TX/RX Console", self)
        self.serial_dock.setWidget(self.serial_console)
        self.serial_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.serial_dock)
        self.serial_dock.hide()
        self.console_timer = QTimer(self)
        self.console_timer.setInterval(500)
        self.console_timer.timeout.connect(self._refresh_serial_console)
        self.console_timer.start()

        self._create_menu()
        self._wire_signals()
        self._load_demo_if_present()
        self._update_file_labels()
        self._update_flash_state()
        self._load_voices()
        if auto_start_mock:
            QTimer.singleShot(250, self._auto_start_mock)

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        for text, slot, shortcut in (
            ("Open BIN…", self.open_bin, "Ctrl+O"),
            ("Open XDF…", self.open_xdf, "Ctrl+Alt+O"),
            ("Save BIN", self.save_bin, "Ctrl+S"),
        ):
            action = QAction(text, self)
            action.triggered.connect(slot)
            if shortcut:
                action.setShortcut(shortcut)
            file_menu.addAction(action)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        connection_menu = self.menuBar().addMenu("Connection")
        connect_action = QAction("Connect / Disconnect", self)
        connect_action.triggered.connect(self.toggle_connection)
        connection_menu.addAction(connect_action)
        refresh_action = QAction("Refresh COM Ports", self)
        refresh_action.triggered.connect(self.refresh_ports)
        connection_menu.addAction(refresh_action)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.serial_dock.toggleViewAction())

    def _wire_signals(self) -> None:
        self.welcome.interface_changed.connect(self.set_interface)
        self.welcome.profile_changed.connect(self.set_profile)
        self.welcome.refresh_requested.connect(self.refresh_ports)
        self.welcome.connect_requested.connect(self.toggle_connection)
        self.welcome.vehicle_info_requested.connect(self.read_vehicle_info)
        self.welcome.open_bin_requested.connect(self.open_bin)
        self.welcome.open_xdf_requested.connect(self.open_xdf)
        self.welcome.save_requested.connect(self.save_bin)
        self.welcome.flash_requested.connect(self.flash_image)
        self.welcome.voice_test_requested.connect(self._test_voice)

        self.tuning.table_selected.connect(self.select_table)
        self.tuning.error_occurred.connect(lambda msg: show_error(self, "Tuning Error", msg))
        self.tuning.map_changed.connect(self._map_changed)

        self.logger.run_toggled.connect(self._run_toggled)
        self.logger.play_requested.connect(self._play_requested)


    def _load_voices(self) -> None:
        self.welcome.voice_combo.clear()
        self.welcome.voice_combo.addItems(list_voices())

    def _test_voice(self, voice_name: str) -> None:
        ok = speak("พร้อมใช้งานระบบเสียง PTS ECU Tuning", voice_name)
        if not ok:
            self.statusBar().showMessage("TTS is available on Windows", 4000)

    def _auto_start_mock(self) -> None:
        if self.welcome.interface_combo.currentText() != "Mock":
            return
        if not self.backend.is_connected():
            self._connect_current_backend(show_dialog=False)
        if self.backend.is_connected() and not self.logger.run_btn.isChecked():
            self.logger.run_btn.setChecked(True)

    def set_interface(self, name: str) -> None:
        if self.state.flashing:
            return
        if self.backend.is_connected():
            self.disconnect_backend()
        if name == "Serial K-Line":
            self.backend = SerialInterface()
            self.state.backend_name = "Serial K-Line"
            self._select_profile_combo("generic-kline-read-only")
            self.state.ecu_profile = generic_kline_read_only_profile()
            self.refresh_ports(show_dialog=False)
        else:
            self.backend = MockInterface(seed=7)
            self.state.backend_name = "Mock"
            self._select_profile_combo("mock-demo-64")
            self.state.ecu_profile = mock_demo_profile()
        self.welcome.set_status("Offline", False)
        self._update_flash_state()

    def _select_profile_combo(self, profile_id: str) -> None:
        combo = self.welcome.profile_combo
        combo.blockSignals(True)
        try:
            for i in range(combo.count()):
                if combo.itemData(i) == profile_id:
                    combo.setCurrentIndex(i)
                    break
        finally:
            combo.blockSignals(False)

    def set_profile(self, profile_id: str) -> None:
        profile = self.profiles.get(profile_id)
        if profile is not None:
            self.state.ecu_profile = profile
        self._update_flash_state()

    def refresh_ports(self, show_dialog: bool = True) -> None:
        try:
            ports = SerialInterface.list_ports()
            self.welcome.set_ports(ports)
            if not ports:
                self.statusBar().showMessage("No serial COM ports detected", 4000)
            else:
                self.statusBar().showMessage(f"Detected {len(ports)} serial port(s)", 4000)
        except Exception as exc:
            self.welcome.set_ports([])
            if show_dialog:
                show_error(self, "COM Port Detection", str(exc))
            else:
                self.statusBar().showMessage(str(exc), 5000)

    def toggle_connection(self) -> None:
        if self.backend.is_connected():
            self.disconnect_backend()
        else:
            self._connect_current_backend(show_dialog=True)

    def _connect_current_backend(self, show_dialog: bool) -> None:
        try:
            if isinstance(self.backend, SerialInterface):
                port = self.welcome.selected_port() or None
                self.backend.connect(port=port, baudrate=self.state.ecu_profile.baudrate if self.state.ecu_profile else 10400)
                state_text = "Serial Connected"
            else:
                self.backend.connect()
                state_text = "Mock Connected"
            self.state.connection_state = state_text
            self.welcome.set_status(state_text, True)
            self.statusBar().showMessage(state_text, 3000)
            self._update_flash_state()
        except Exception as exc:
            self.state.connection_state = "Error"
            self.welcome.set_status("Error", False)
            if show_dialog:
                show_error(self, "Connection Error", str(exc))

    def disconnect_backend(self) -> None:
        if self.state.logging:
            self.stop_logging(wait=True)
        try:
            self.backend.disconnect()
        except Exception as exc:
            show_error(self, "Disconnect Error", str(exc))
        self.state.connection_state = "Offline"
        self.welcome.set_status("Offline", False)
        self._update_flash_state()

    def read_vehicle_info(self) -> None:
        try:
            if isinstance(self.backend, SerialInterface):
                if self.state.ecu_profile is None:
                    raise RuntimeError("Select an ECU profile before KWP initialization")
                candidate, response = self.backend.initialize_kwp_profile(self.state.ecu_profile)
                info = {
                    "interface": self.backend.port or "Serial",
                    "profile": self.state.ecu_profile.profile_id,
                    "baudrate": candidate.baudrate,
                    "initialization": candidate.name,
                    "response_hex": response.hex(" ").upper() or "<no data>",
                }
                self.welcome.set_vehicle_info(info)
                self.serial_dock.show()
            else:
                info = self.backend.read_vehicle_info()
                self.welcome.set_vehicle_info(info)
        except Exception as exc:
            show_error(self, "Vehicle Information / KWP Init", str(exc))

    def _last_folder(self) -> str:
        return self.state.last_folder or str(Path.home())

    def _remember_folder(self, path: str | Path) -> None:
        folder = str(Path(path).resolve().parent)
        self.state.last_folder = folder
        self.settings.setValue("lastFolder", folder)

    def open_bin(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open ECU BIN", self._last_folder(), "ECU Binary (*.bin *.BIN);;All Files (*)")
        if path:
            self.load_bin_path(path)

    def load_bin_path(self, path: str | Path) -> None:
        try:
            self.state.bin_image = BinImage.from_file(path)
            self._remember_folder(path)
            self._update_file_labels()
            self._select_first_table_if_possible()
            self._update_flash_state()
        except Exception as exc:
            show_error(self, "Open BIN", str(exc))

    def open_xdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open XDF", self._last_folder(), "XDF/XML (*.xdf *.xml *.XDF);;All Files (*)")
        if path:
            self.load_xdf_path(path)

    def load_xdf_path(self, path: str | Path) -> None:
        try:
            doc = parse_xdf(path)
            self.state.xdf_document = doc
            self._remember_folder(path)
            self.tuning.load_document(doc)
            self._update_file_labels()
            self._select_first_table_if_possible()
            if doc.warnings:
                self.statusBar().showMessage(f"XDF loaded with {len(doc.warnings)} warning(s)", 5000)
        except Exception as exc:
            show_error(self, "Open XDF", str(exc))

    def _select_first_table_if_possible(self) -> None:
        if self.state.bin_image is None or self.state.xdf_document is None or not self.state.xdf_document.tables:
            return
        self.select_table(self.state.xdf_document.tables[0])

    def select_table(self, table) -> None:
        if self.state.bin_image is None:
            show_error(self, "Tuning Grid", "Open a BIN file before loading a calibration map.")
            return
        try:
            cmap = CalibrationMap(self.state.bin_image, table)
            self.state.selected_table = table
            self.tuning.load_map(cmap)
            self.tabs.setCurrentWidget(self.tuning)
        except Exception as exc:
            show_error(self, "Map Load Error", str(exc))

    def save_bin(self) -> None:
        image = self.state.bin_image
        if image is None:
            show_error(self, "Save BIN", "No BIN is loaded.")
            return
        demo_dir = (Path(__file__).resolve().parent.parent / "demo").resolve()
        source = image.source_path.resolve() if image.source_path else None
        if source is None or demo_dir in source.parents:
            path, _ = QFileDialog.getSaveFileName(self, "Save ECU BIN As", self._last_folder(), "ECU Binary (*.bin)")
            if not path:
                return
            target = Path(path)
        else:
            target = source
        try:
            image.save(target, backup_existing=True)
            self._remember_folder(target)
            self.statusBar().showMessage(f"Saved {target.name}", 4000)
            self._update_file_labels()
        except Exception as exc:
            show_error(self, "Save BIN", str(exc))

    def _map_changed(self) -> None:
        self._update_file_labels()
        self._update_flash_state()

    def _update_file_labels(self) -> None:
        bin_name = self.state.bin_image.source_path.name if self.state.bin_image and self.state.bin_image.source_path else ("In-memory BIN" if self.state.bin_image else None)
        xdf_name = self.state.xdf_document.source_path.name if self.state.xdf_document and self.state.xdf_document.source_path else None
        self.welcome.set_file_names(bin_name, xdf_name, self.state.dirty)

    def _run_toggled(self, checked: bool) -> None:
        if checked:
            if not self.backend.is_connected():
                self._connect_current_backend(show_dialog=True)
            if self.backend.is_connected():
                self.start_logging()
            else:
                self.logger.run_btn.blockSignals(True)
                self.logger.run_btn.setChecked(False)
                self.logger.run_btn.blockSignals(False)
        else:
            self.stop_logging(wait=False)

    def start_logging(self) -> None:
        if self.state.logging or self.state.flashing:
            return
        if not self.backend.is_connected():
            show_error(self, "Datalog", "Connect an interface first.")
            return
        self.logger_worker = LoggerWorker(self.backend, poll_interval=0.05)
        self.logger_thread = QThread(self)
        self.logger_worker.moveToThread(self.logger_thread)
        self.logger_thread.started.connect(self.logger_worker.run)
        self.logger_worker.sample_received.connect(self._sample_received)
        self.logger_worker.status_changed.connect(self.logger.graph_status.setText)
        self.logger_worker.error_occurred.connect(self._logger_error)
        self.logger_worker.stopped.connect(self.logger_thread.quit)
        self.logger_thread.finished.connect(self._logger_finished)
        self.state.logging = True
        self.state.connection_state = "Logging"
        self.welcome.set_status("Logging", True)
        self.logger_thread.start()

    def stop_logging(self, wait: bool = False) -> bool:
        worker = self.logger_worker
        thread = self.logger_thread
        if worker is not None:
            worker.request_stop()
        if wait and thread is not None and thread.isRunning():
            if not thread.wait(2500):
                return False
        return True

    def _logger_finished(self) -> None:
        self.state.logging = False
        self.logger_worker = None
        self.logger_thread = None
        self.logger.run_btn.blockSignals(True)
        self.logger.run_btn.setChecked(False)
        self.logger.run_btn.setText("RUN")
        self.logger.run_btn.blockSignals(False)
        if self.backend.is_connected():
            text = "Mock Connected" if isinstance(self.backend, MockInterface) else "Serial Connected"
            self.state.connection_state = text
            self.welcome.set_status(text, True)
        else:
            self.state.connection_state = "Offline"
            self.welcome.set_status("Offline", False)
        self._update_flash_state()

    def _logger_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Logger error: {message}", 6000)

    def _sample_received(self, sample) -> None:
        self.logger.append_sample(sample)
        self.tuning.trace_sample(sample.rpm, sample.tps)

    def _play_requested(self) -> None:
        if self.state.logging:
            self.stop_logging(wait=True)
        self.logger.start_replay()

    def _update_flash_state(self) -> None:
        if self.state.bin_image is None or self.state.ecu_profile is None:
            self.welcome.flash_btn.setEnabled(False)
            self.welcome.flash_btn.setToolTip("Load a BIN and select an ECU profile")
            return
        result = validate_flash_preconditions(self.state.bin_image, self.state.ecu_profile, self.backend)
        enabled = result.ok and not self.state.flashing
        self.welcome.flash_btn.setEnabled(enabled)
        details = list(result.errors) + list(result.warnings)
        self.welcome.flash_btn.setToolTip("\n".join(details) if details else "Flash preconditions satisfied")

    def flash_image(self) -> None:
        if self.state.bin_image is None or self.state.ecu_profile is None:
            show_error(self, "Flash ECU", "Load a BIN and select a supported ECU profile first.")
            return
        check = validate_flash_preconditions(self.state.bin_image, self.state.ecu_profile, self.backend)
        if not check.ok:
            show_error(self, "Flash Preconditions", "\n".join(check.errors))
            return
        if not confirm_flash(self, self.state.ecu_profile.profile_id, check.warnings):
            return
        if self.state.logging and not self.stop_logging(wait=True):
            show_error(self, "Flash ECU", "Logger thread did not stop cleanly; flash cancelled.")
            return
        self.state.flashing = True
        self.welcome.set_status("Flashing", True)
        self._update_flash_state()

        self.flash_worker = FlashWorker(self.backend, self.state.bin_image, self.state.ecu_profile)
        self.flash_thread = QThread(self)
        self.flash_worker.moveToThread(self.flash_thread)
        self.flash_thread.started.connect(self.flash_worker.run)
        self.flash_worker.progress.connect(self._flash_progress)
        self.flash_worker.status_changed.connect(lambda msg: self.statusBar().showMessage(msg))
        self.flash_worker.error_occurred.connect(lambda msg: show_error(self, "Flash Error", msg))
        self.flash_worker.finished.connect(self.flash_thread.quit)
        self.flash_worker.finished.connect(self._flash_finished)
        self.flash_thread.finished.connect(self._flash_thread_finished)
        self.flash_thread.start()

    def _flash_progress(self, value: int, message: str) -> None:
        self.statusBar().showMessage(f"Flash {value}% — {message}")
        self.welcome.set_status(f"Flashing {value}%", True)

    def _flash_finished(self, success: bool) -> None:
        self.state.flashing = False
        if success:
            self.welcome.set_status("Flash Verified", True)
            show_info(self, "Flash Complete", "The image was written and verified by the selected backend/profile.")
        else:
            self.welcome.set_status("Flash Stopped", self.backend.is_connected())
        self._update_flash_state()

    def _flash_thread_finished(self) -> None:
        self.flash_worker = None
        self.flash_thread = None

    def _refresh_serial_console(self) -> None:
        if isinstance(self.backend, SerialInterface):
            self.serial_console.set_entries(self.backend.frame_log)

    def _load_demo_if_present(self) -> None:
        root = Path(__file__).resolve().parent.parent
        demo_bin = root / "demo" / "demo.bin"
        demo_xdf = root / "demo" / "demo.xdf"
        if demo_bin.exists():
            try:
                self.state.bin_image = BinImage.from_file(demo_bin)
            except Exception:
                pass
        if demo_xdf.exists():
            try:
                self.state.xdf_document = parse_xdf(demo_xdf)
                self.tuning.load_document(self.state.xdf_document)
            except Exception:
                pass
        self._select_first_table_if_possible()

    def closeEvent(self, event) -> None:
        if self.state.flashing:
            QMessageBox.warning(self, "Flash In Progress", "The application cannot close during an active flash operation.")
            event.ignore()
            return
        if self.state.logging and not self.stop_logging(wait=True):
            QMessageBox.warning(self, "Logger Still Running", "The logger worker did not stop cleanly. Disconnect the interface and try again.")
            event.ignore()
            return
        try:
            if self.backend.is_connected():
                self.backend.disconnect()
        finally:
            event.accept()
