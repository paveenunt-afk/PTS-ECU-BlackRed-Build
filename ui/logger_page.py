from __future__ import annotations

from collections import deque
import time

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
import pyqtgraph as pg


class LoggerPage(QWidget):
    run_toggled = pyqtSignal(bool)
    clear_requested = pyqtSignal()
    play_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        graph_panel = QFrame()
        graph_panel.setObjectName("panel")
        graph_layout = QVBoxLayout(graph_panel)
        title = QLabel("บันทึกข้อมูลเรียลไทม์ / กราฟ DYNO")
        title.setObjectName("sectionTitle")
        graph_layout.addWidget(title)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#02070D")
        self.plot.showGrid(x=True, y=True, alpha=0.22)
        self.plot.setLabel("bottom", "รอบเครื่องยนต์", units="RPM")
        self.plot.setLabel("left", "ตำแหน่งคันเร่ง", units="%")
        self.plot.setXRange(0, 13000, padding=0)
        self.plot.setYRange(0, 100, padding=0.03)
        self.plot.setMouseEnabled(x=True, y=True)
        self.curve = self.plot.plot([], [], pen=pg.mkPen("#FF3038", width=2))
        graph_layout.addWidget(self.plot, 1)
        self.graph_status = QLabel("พร้อมใช้งาน — โหมดจำลองทำงานได้โดยไม่ต้องต่อรถ")
        self.graph_status.setObjectName("statusStrip")
        graph_layout.addWidget(self.graph_status)
        root.addWidget(graph_panel, 1)

        controls = QFrame()
        controls.setObjectName("panel")
        controls.setFixedWidth(220)
        ctl = QVBoxLayout(controls)
        ctl.addWidget(QLabel("ค่าข้อมูลสด"), 0)
        self.rpm_card = QLabel("0\nRPM")
        self.rpm_card.setObjectName("valueCard")
        self.tps_card = QLabel("0.0\nTPS %")
        self.tps_card.setObjectName("valueCard")
        self.rpm_card.setMinimumHeight(90)
        self.tps_card.setMinimumHeight(90)
        ctl.addWidget(self.rpm_card)
        ctl.addWidget(self.tps_card)
        ctl.addStretch(1)
        self.run_btn = QPushButton("เริ่ม")
        self.run_btn.setCheckable(True)
        self.run_btn.setObjectName("primaryButton")
        self.clear_btn = QPushButton("ล้างข้อมูล")
        self.play_btn = QPushButton("เล่นย้อนหลัง")
        for b in (self.run_btn, self.clear_btn, self.play_btn):
            b.setMinimumHeight(52)
        self.run_btn.toggled.connect(self._run_changed)
        self.clear_btn.clicked.connect(self._clear_clicked)
        self.play_btn.clicked.connect(self._play_clicked)
        ctl.addWidget(self.run_btn)
        ctl.addWidget(self.clear_btn)
        ctl.addWidget(self.play_btn)
        root.addWidget(controls)

        self._rpm = deque(maxlen=5000)
        self._tps = deque(maxlen=5000)
        self._recording: list[tuple[float, float]] = []
        self._last_draw = 0.0
        self._replay_data: list[tuple[float, float]] = []
        self._replay_index = 0
        self._replay_timer = QTimer(self)
        self._replay_timer.setInterval(45)
        self._replay_timer.timeout.connect(self._replay_tick)

    def _run_changed(self, checked: bool) -> None:
        self.run_btn.setText("หยุด" if checked else "เริ่ม")
        if checked:
            self.stop_replay()
        self.run_toggled.emit(checked)

    def _clear_clicked(self) -> None:
        self.clear_data()
        self.clear_requested.emit()

    def _play_clicked(self) -> None:
        self.play_requested.emit()

    def append_sample(self, sample, *, record: bool = True) -> None:
        rpm = float(sample.rpm)
        tps = float(sample.tps)
        self._rpm.append(rpm)
        self._tps.append(tps)
        if record:
            self._recording.append((rpm, tps))
            if len(self._recording) > 10000:
                del self._recording[:2000]
        self.rpm_card.setText(f"{rpm:,.0f}\nRPM")
        self.tps_card.setText(f"{tps:.1f}\nTPS %")
        now = time.monotonic()
        if now - self._last_draw >= 0.04:
            self.curve.setData(list(self._rpm), list(self._tps))
            self._last_draw = now

    def clear_data(self) -> None:
        self.stop_replay()
        self._rpm.clear()
        self._tps.clear()
        self._recording.clear()
        self.curve.setData([], [])
        self.rpm_card.setText("0\nRPM")
        self.tps_card.setText("0.0\nTPS %")
        self.graph_status.setText("ล้างข้อมูลกราฟแล้ว")

    def start_replay(self) -> bool:
        if not self._recording:
            self.graph_status.setText("ยังไม่มีข้อมูลที่บันทึกไว้สำหรับเล่นย้อนหลัง")
            return False
        self._replay_data = list(self._recording)
        self._replay_index = 0
        self._rpm.clear()
        self._tps.clear()
        self.curve.setData([], [])
        self.graph_status.setText(f"กำลังเล่นย้อนหลัง — {len(self._replay_data)} ตัวอย่าง")
        self._replay_timer.start()
        return True

    def stop_replay(self) -> None:
        if self._replay_timer.isActive():
            self._replay_timer.stop()

    def _replay_tick(self) -> None:
        if self._replay_index >= len(self._replay_data):
            self.stop_replay()
            self.graph_status.setText("เล่นข้อมูลย้อนหลังเสร็จแล้ว")
            return
        rpm, tps = self._replay_data[self._replay_index]
        self._replay_index += 1
        self._rpm.append(rpm)
        self._tps.append(tps)
        self.rpm_card.setText(f"{rpm:,.0f}\nRPM")
        self.tps_card.setText(f"{tps:.1f}\nTPS %")
        self.curve.setData(list(self._rpm), list(self._tps))
