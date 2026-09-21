from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSlider, QVBoxLayout, QWidget
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
    voice_test_requested = pyqtSignal(str, int, int)
    theme_changed = pyqtSignal(str)

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
        label = QLabel("ข้อมูลรถ / ECU")
        label.setObjectName("sectionTitle")
        info_layout.addWidget(label)
        self.vehicle_info = QLabel("ยังไม่มีข้อมูลรถ\n\nกรุณาเชื่อมต่อโหมดจำลองหรืออุปกรณ์ที่รองรับ")
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
        background = Path(__file__).resolve().parent.parent / "assets" / "ecu_tuning_background_v2.jpg"
        if background.exists():
            center.setStyleSheet(
                "QFrame#heroPanel { border-image: url('" + background.as_posix() + "') 0 0 0 0 stretch stretch; }"
                "QLabel { background: rgba(0, 0, 0, 145); padding: 6px; border-radius: 6px; }"
            )
        center_layout = QVBoxLayout(center)
        center_layout.setAlignment(Qt.AlignCenter)
        brand = QLabel("PTS ECU LINK")
        brand.setAlignment(Qt.AlignCenter)
        brand.setObjectName("brandTitle")
        subtitle = QLabel("ปรับจูน ECU  •  บันทึกข้อมูล  •  เขียนซอฟต์แวร์")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("brandSubtitle")
        self.status = QLabel("ออฟไลน์")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setObjectName("statusBadge")
        warning = QLabel("การใช้งาน K-Line จริงต้องใช้อินเทอร์เฟซมาตรฐานรถยนต์ ห้ามต่อ USB-TTL เข้าระบบ 12 โวลต์โดยตรง")
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
        title = QLabel("การเชื่อมต่อและเสียง")
        title.setObjectName("sectionTitle")
        c.addWidget(title)
        c.addWidget(QLabel("อินเทอร์เฟซ"))
        self.interface_combo = QComboBox()
        self.interface_combo.addItems(["Mock", "Serial K-Line"])
        self.interface_combo.currentTextChanged.connect(self.interface_changed)
        c.addWidget(self.interface_combo)
        c.addWidget(QLabel("โปรไฟล์ ECU"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Mock Demo 64-byte", "mock-demo-64")
        self.profile_combo.addItem("Generic K-Line (Read Only)", "generic-kline-read-only")
        self.profile_combo.currentIndexChanged.connect(self._profile_index_changed)
        c.addWidget(self.profile_combo)
        c.addWidget(QLabel("พอร์ต COM"))
        row = QHBoxLayout()
        self.port_combo = QComboBox()
        row.addWidget(self.port_combo, 1)
        refresh = QPushButton("ค้นหาใหม่")
        refresh.clicked.connect(self.refresh_requested)
        row.addWidget(refresh)
        c.addLayout(row)
        self.connect_btn = QPushButton("เชื่อมต่อ")
        self.connect_btn.setObjectName("primaryButton")
        self.connect_btn.clicked.connect(self.connect_requested)
        c.addWidget(self.connect_btn)
        read_info = QPushButton("อ่านข้อมูลรถ")
        read_info.clicked.connect(self.vehicle_info_requested)
        c.addWidget(read_info)
        c.addWidget(QLabel("เสียงบุคคล (หญิง/ชายตามเสียงใน Windows)"))
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("เสียงเริ่มต้นของระบบ")
        c.addWidget(self.voice_combo)
        voice_options = QHBoxLayout()
        voice_options.addWidget(QLabel("ความเร็ว"))
        self.voice_rate = QComboBox()
        for label, value in (("ช้า", -2), ("ปกติ", 1), ("เร็ว", 3)):
            self.voice_rate.addItem(label, value)
        self.voice_rate.setCurrentIndex(1)
        voice_options.addWidget(self.voice_rate)
        voice_options.addWidget(QLabel("ดัง"))
        self.voice_volume = QSlider(Qt.Horizontal)
        self.voice_volume.setRange(20, 100)
        self.voice_volume.setValue(100)
        voice_options.addWidget(self.voice_volume)
        c.addLayout(voice_options)
        self.voice_test_btn = QPushButton("ทดสอบเสียงพูด")
        self.voice_test_btn.clicked.connect(lambda: self.voice_test_requested.emit(
            self.voice_combo.currentText(), int(self.voice_rate.currentData()), self.voice_volume.value()))
        c.addWidget(self.voice_test_btn)
        c.addWidget(QLabel("โทนสีหน้าต่าง"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["ดำ–แดง", "ดำ–ฟ้า", "ดำ–ส้ม", "ดำ–เขียว"])
        self.theme_combo.currentTextChanged.connect(self.theme_changed)
        c.addWidget(self.theme_combo)
        c.addStretch(1)
        hero.addWidget(connection, 0)

        actions = QFrame()
        actions.setObjectName("actionPanel")
        action_layout = QGridLayout(actions)
        self.open_bin_btn = QPushButton("เปิดไฟล์ BIN")
        self.open_xdf_btn = QPushButton("เปิดไฟล์ XDF")
        self.save_btn = QPushButton("บันทึก BIN")
        self.flash_btn = QPushButton("เขียนข้อมูล ECU")
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
        translations = {
            "Offline": "ออฟไลน์", "Error": "เกิดข้อผิดพลาด",
            "Mock Connected": "เชื่อมต่อโหมดจำลองแล้ว",
            "Serial Connected": "เชื่อมต่อ Serial แล้ว",
            "Logging": "กำลังบันทึกข้อมูล", "Flashing": "กำลังเขียน ECU",
            "Flash Verified": "ตรวจสอบการเขียนสำเร็จ", "Flash Stopped": "หยุดการเขียนแล้ว",
        }
        self.status.setText(translations.get(text, text).upper())
        self.status.setProperty("connected", connected)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.connect_btn.setText("ตัดการเชื่อมต่อ" if connected else "เชื่อมต่อ")

    def set_vehicle_info(self, info: dict) -> None:
        lines = [f"{str(k).replace('_', ' ').title()}: {v}" for k, v in info.items()]
        self.vehicle_info.setText("\n".join(lines) if lines else "ไม่พบข้อมูลรถ")

    def set_file_names(self, bin_name: str | None, xdf_name: str | None, dirty: bool = False) -> None:
        mark = " *" if dirty and bin_name else ""
        self.bin_label.setText(f"BIN: {bin_name or '—'}{mark}")
        self.xdf_label.setText(f"XDF: {xdf_name or '—'}")
