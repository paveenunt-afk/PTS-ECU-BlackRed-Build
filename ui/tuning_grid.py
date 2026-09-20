from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
)

from core.map_model import CalibrationMap, MapEdit


class LiveCellDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.live_cell: tuple[int, int] | None = None

    def paint(self, painter, option: QStyleOptionViewItem, index):
        super().paint(painter, option, index)
        if self.live_cell == (index.row(), index.column()):
            painter.save()
            painter.setPen(QPen(QColor("#FF3038"), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(option.rect.adjusted(2, 2, -2, -2))
            painter.restore()


class TuningGrid(QTableWidget):
    error_occurred = pyqtSignal(str)
    edit_applied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        self.setAlternatingRowColors(False)
        self.setShowGrid(True)
        self.verticalHeader().setDefaultSectionSize(32)
        self.horizontalHeader().setDefaultSectionSize(70)
        self._map: CalibrationMap | None = None
        self._updating = False
        self._undo: list[MapEdit] = []
        self._redo: list[MapEdit] = []
        self._delegate = LiveCellDelegate(self)
        self.setItemDelegate(self._delegate)
        self.itemChanged.connect(self._on_item_changed)

    @property
    def calibration_map(self) -> CalibrationMap | None:
        return self._map

    def load_map(self, calibration_map: CalibrationMap) -> None:
        self._map = calibration_map
        self._undo.clear()
        self._redo.clear()
        self._updating = True
        try:
            self.clear()
            self.setRowCount(calibration_map.table.rows)
            self.setColumnCount(calibration_map.table.columns)
            self.setVerticalHeaderLabels([self._fmt(v) for v in calibration_map.row_headers])
            self.setHorizontalHeaderLabels([self._fmt(v) for v in calibration_map.column_headers])
            for r, row in enumerate(calibration_map.values()):
                for c, value in enumerate(row):
                    item = QTableWidgetItem(self._fmt(value))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setData(Qt.UserRole, float(value))
                    self.setItem(r, c, item)
            self.recolor()
        finally:
            self._updating = False

    @staticmethod
    def _fmt(value: float) -> str:
        text = f"{float(value):.3f}".rstrip("0").rstrip(".")
        return text if text else "0"

    def recolor(self) -> None:
        if self._map is None:
            return
        values = [self._map.display_value(r, c) for r in range(self.rowCount()) for c in range(self.columnCount())]
        if not values:
            return
        lo, hi = min(values), max(values)
        span = hi - lo or 1.0
        self._updating = True
        try:
            for r in range(self.rowCount()):
                for c in range(self.columnCount()):
                    value = self._map.display_value(r, c)
                    t = max(0.0, min(1.0, (value - lo) / span))
                    # HSV: cyan/blue -> green -> yellow -> red.
                    hue = int(190 * (1.0 - t))
                    color = QColor.fromHsv(hue, 200, 165)
                    item = self.item(r, c)
                    if item:
                        item.setBackground(QBrush(color))
                        item.setForeground(QBrush(QColor("#F7FEFF")))
                        item.setText(self._fmt(value))
                        item.setData(Qt.UserRole, float(value))
        finally:
            self._updating = False

    def selected_cells(self) -> list[tuple[int, int]]:
        return sorted({(idx.row(), idx.column()) for idx in self.selectedIndexes()})

    def apply_quick_edit(self, formula: str) -> None:
        if self._map is None:
            self.error_occurred.emit("No calibration map is loaded")
            return
        cells = self.selected_cells()
        try:
            edit = self._map.apply_formula(cells, formula)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return
        self._undo.append(edit)
        self._redo.clear()
        self.recolor()
        self.edit_applied.emit()

    def undo(self) -> None:
        if self._map is None or not self._undo:
            return
        edit = self._undo.pop()
        self._map.undo_edit(edit)
        self._redo.append(edit)
        self.recolor()
        self.edit_applied.emit()

    def redo(self) -> None:
        if self._map is None or not self._redo:
            return
        edit = self._redo.pop()
        self._map.redo_edit(edit)
        self._undo.append(edit)
        self.recolor()
        self.edit_applied.emit()

    def set_live_cell(self, row: int | None, column: int | None = None) -> None:
        self._delegate.live_cell = None if row is None or column is None else (int(row), int(column))
        self.viewport().update()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or self._map is None:
            return
        row, col = item.row(), item.column()
        old = self._map.display_value(row, col)
        try:
            value = float(item.text())
            edit = self._map.set_display_value(row, col, value)
        except Exception as exc:
            self._updating = True
            item.setText(self._fmt(old))
            self._updating = False
            self.error_occurred.emit(str(exc))
            return
        self._undo.append(edit)
        self._redo.clear()
        self.recolor()
        self.edit_applied.emit()
