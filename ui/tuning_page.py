from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

from core.map_model import CalibrationMap
from core.xdf_parser import XdfDocument
from ui.tuning_grid import TuningGrid


class TuningPage(QWidget):
    table_selected = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    map_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        left = QFrame()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        title = QLabel("รายการพารามิเตอร์")
        title.setObjectName("sectionTitle")
        left_layout.addWidget(title)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._tree_clicked)
        left_layout.addWidget(self.tree)
        splitter.addWidget(left)

        right = QFrame()
        right.setObjectName("panel")
        right_layout = QVBoxLayout(right)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("ปรับค่าแบบรวดเร็ว"))
        self.formula = QLineEdit("+1.5")
        self.formula.setPlaceholderText("+1.5   -2   *1.1   /1.05   หรือใส่ค่าโดยตรง")
        self.formula.returnPressed.connect(self._apply_formula)
        toolbar.addWidget(self.formula, 1)
        apply_btn = QPushButton("ใช้กับช่องที่เลือก")
        apply_btn.clicked.connect(self._apply_formula)
        undo_btn = QPushButton("ย้อนกลับ")
        undo_btn.clicked.connect(self._undo)
        redo_btn = QPushButton("ทำซ้ำ")
        redo_btn.clicked.connect(self._redo)
        toolbar.addWidget(apply_btn)
        toolbar.addWidget(undo_btn)
        toolbar.addWidget(redo_btn)
        right_layout.addLayout(toolbar)

        self.map_title = QLabel("ยังไม่ได้เลือกตาราง")
        self.map_title.setObjectName("mapTitle")
        right_layout.addWidget(self.map_title)
        self.grid = TuningGrid()
        self.grid.error_occurred.connect(self.error_occurred)
        self.grid.edit_applied.connect(self.map_changed)
        right_layout.addWidget(self.grid, 1)
        self.status = QLabel("RPM: --    TPS: --    Cell: --")
        self.status.setObjectName("statusStrip")
        right_layout.addWidget(self.status)
        splitter.addWidget(right)
        splitter.setSizes([250, 1050])
        self._items: dict[int, object] = {}

    def load_document(self, doc: XdfDocument) -> None:
        self.tree.clear()
        self._items.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        for idx, table in enumerate(doc.tables):
            group_name = table.category or "แผนที่ปรับจูน"
            parent = groups.get(group_name)
            if parent is None:
                parent = QTreeWidgetItem([group_name])
                parent.setExpanded(True)
                groups[group_name] = parent
                self.tree.addTopLevelItem(parent)
            item = QTreeWidgetItem([table.name])
            item.setData(0, Qt.UserRole, idx)
            parent.addChild(item)
            self._items[idx] = table
        self.tree.expandAll()

    def _tree_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        idx = item.data(0, Qt.UserRole)
        if idx is not None and idx in self._items:
            self.table_selected.emit(self._items[idx])

    def load_map(self, calibration_map: CalibrationMap) -> None:
        self.grid.load_map(calibration_map)
        units = f" [{calibration_map.table.units}]" if calibration_map.table.units else ""
        self.map_title.setText(f"{calibration_map.table.name}{units}   @ 0x{calibration_map.table.address:X}")

    def _apply_formula(self) -> None:
        self.grid.apply_quick_edit(self.formula.text())

    def _undo(self) -> None:
        self.grid.undo()

    def _redo(self) -> None:
        self.grid.redo()

    def trace_sample(self, rpm: float, tps: float) -> None:
        cmap = self.grid.calibration_map
        if cmap is None:
            self.status.setText(f"RPM: {rpm:,.0f}    TPS: {tps:.1f}%    Cell: --")
            return
        row, col = cmap.nearest_cell(rpm, tps)
        self.grid.set_live_cell(row, col)
        self.status.setText(f"RPM: {rpm:,.0f}    TPS: {tps:.1f}%    Cell: R{row + 1} C{col + 1}")
