from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget
)


class WelcomePage(QWidget):
    interface_changed = pyqtSignal(str)
    profile_changed = pyqtSignal(str)
    refresh_requested = pyqtSignal()
    connect_requested = pyqtSignal()
    vehicle_info_requested = pyqtSignal()
    open_bin_requested = pyqtSignal()
    open_xdf_requested = pyqtSignal()
    save_requested = pyqtSignal()
    flash_requested = pyqtSignal()
    voice_test_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        hero = QHBoxLayout()
        root.addLayout(hero, 1)

        info_panel = QFrame()
        info_panel.setObjectName("panel")
        info_panel.setMinimumWidth(300)
        info_layout = QVBoxLayout(info_panel)
        label = QLabel("VEHICLE / ECU")
        label.setObjectName("sectionTitle")
        info_layout.addWidget(label)
        self.vehicle_info = QLabel("No vehicle information\n\nConnect Mock Mode or a supported interface.")
        self.vehicle_info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.vehicle_info.setWordWrap(True)
        self.vehicle_info.setObjectName("vehicleInfo")
        info_layout.addWidget(self.vehicle_info, 1)
        self.bin_label = QLabel("BIN: —")
        self.xdf_label = QLabel("XDF: —")
        self.bin_label.setWordWrap(True)
        self.xdf_label.setWordWrap(True)
        info_layout.addWidget(self.bin_label)
        info_layout.addWidget(self.xdf_label)
        hero.addWidget(info_panel, 0)

        center = QFrame()
        center.setObjectName("heroPanel")
        center_layout = QVBoxLayout(center)
        center_layout.setAlignment(Qt.AlignCenter)
        brand = QLabel("PTS ECU LINK")
        brand.setAlignment(Qt.AlignCenter)
        brand.setObjectName("brandTitle")
        subtitle = QLabel("ECU TUNING  •  DATA LOGGER  •  SOFTWARE FLASH")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("brandSubtitle")
        self.status = QLabel("OFFLINE")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setObjectName("statusBadge")
        warning = QLabel("Real K-Line use requires an automotive-rated interface. USB-TTL alone is not assumed safe for a 12 V K-Line bus.")
        warning.setWordWrap(True)
        warning.setAlignment(Qt.AlignCenter)
        warning.setObjectName("warningText")
        center_layout.addStretch(1)
        center_layout.addWidget(brand)
        center_layout.addWidget(subtitle)
        center_layout.addSpacing(24)
        center_layout.addWidget(self.status)
        center_layout.addSpacing(24)
        center_layout.addWidget(warning)
        center_layout.addStretch(1)
        hero.addWidget(center, 1)

        connection = QFrame()
        connection.setObjectName("panel")
        connection.setMinimumWidth(310)
        c = QVBoxLayout(connection)
        title = QLabel("CONNECTION")
        title.setObjectName("sectionTitle")
        c.addWidget(title)
        c.addWidget(QLabel("Interface"))
        self.interface_combo = QComboBox()
        self.interface_combo.addItems(["Mock", "Serial K-Line"])
        self.interface_combo.currentTextChanged.connect(self.interface_changed)
        c.addWidget(self.interface_combo)
        c.addWidget(QLabel("ECU Profile"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Mock Demo 64-byte", "mock-demo-64")
        self.profile_combo.addItem("Generic K-Line (Read Only)", "generic-kline-read-only")
        self.profile_combo.currentIndexChanged.connect(self._profile_index_changed)
        c.addWidget(self.profile_combo)
        c.addWidget(QLabel("COM Port"))
        row = QHBoxLayout()
        self.port_combo = QComboBox()
        row.addWidget(self.port_combo, 1)
        refresh = QPushButton("REFRESH")
        refresh.clicked.connect(self.refresh_requested)
        row.addWidget(refresh)
        c.addLayout(row)
        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.setObjectName("primaryButton")
        self.connect_btn.clicked.connect(self.connect_requested)
        c.addWidget(self.connect_btn)
        read_info = QPushButton("READ VEHICLE INFO")
        read_info.clicked.connect(self.vehicle_info_requested)
        c.addWidget(read_info)
        c.addWidget(QLabel("Thai Voice / Windows Voice"))
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("System default")
        c.addWidget(self.voice_combo)
        self.voice_test_btn = QPushButton("ทดสอบเสียง / TEST VOICE")
        self.voice_test_btn.clicked.connect(lambda: self.voice_test_requested.emit(self.voice_combo.currentText()))
        c.addWidget(self.voice_test_btn)
        c.addStretch(1)
        hero.addWidget(connection, 0)

        actions = QFrame()
        actions.setObjectName("actionPanel")
        action_layout = QGridLayout(actions)
        self.open_bin_btn = QPushButton("OPEN BIN")
        self.open_xdf_btn = QPushButton("OPEN XDF")
        self.save_btn = QPushButton("SAVE BIN")
        self.flash_btn = QPushButton("FLASH ECU")
        self.flash_btn.setObjectName("dangerButton")
        self.open_bin_btn.clicked.connect(self.open_bin_requested)
        self.open_xdf_btn.clicked.connect(self.open_xdf_requested)
        self.save_btn.clicked.connect(self.save_requested)
        self.flash_btn.clicked.connect(self.flash_requested)
        for i, widget in enumerate((self.open_bin_btn, self.open_xdf_btn, self.save_btn, self.flash_btn)):
            widget.setMinimumHeight(48)
            action_layout.addWidget(widget, 0, i)
        root.addWidget(actions)

    def _profile_index_changed(self, index: int) -> None:
        profile_id = self.profile_combo.itemData(index)
        if profile_id:
            self.profile_changed.emit(str(profile_id))

    def selected_port(self) -> str:
        return str(self.port_combo.currentData() or self.port_combo.currentText()).strip()

    def set_ports(self, ports) -> None:
        current = self.selected_port()
        self.port_combo.clear()
        for p in ports:
            label = f"{p.device} — {p.description}" if p.description else p.device
            self.port_combo.addItem(label, p.device)
        if current:
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i) == current:
                    self.port_combo.setCurrentIndex(i)
                    break

    def set_status(self, text: str, connected: bool = False) -> None:
        self.status.setText(text.upper())
        self.status.setProperty("connected", connected)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.connect_btn.setText("DISCONNECT" if connected else "CONNECT")

    def set_vehicle_info(self, info: dict) -> None:
        lines = [f"{str(k).replace('_', ' ').title()}: {v}" for k, v in info.items()]
        self.vehicle_info.setText("\n".join(lines) if lines else "No information returned")

    def set_file_names(self, bin_name: str | None, xdf_name: str | None, dirty: bool = False) -> None:
        mark = " *" if dirty and bin_name else ""
        self.bin_label.setText(f"BIN: {bin_name or '—'}{mark}")
        self.xdf_label.setText(f"XDF: {xdf_name or '—'}")
