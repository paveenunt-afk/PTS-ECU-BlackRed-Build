from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.bin_engine import BinImage, BinError
from core.math_engine import SafeExpression, apply_quick_formula, MathExpressionError
from core.xdf_parser import AxisDefinition, TableDefinition


class MapModelError(ValueError):
    pass


@dataclass(frozen=True)
class CellChange:
    row: int
    column: int
    old_raw: int
    new_raw: int


@dataclass(frozen=True)
class MapEdit:
    changes: tuple[CellChange, ...]


_CODEC_SIZE = {"B": 1, ">H": 2, "<H": 2}
_CODEC_RANGE = {"B": (0, 0xFF), ">H": (0, 0xFFFF), "<H": (0, 0xFFFF)}


class CalibrationMap:
    def __init__(self, image: BinImage, table: TableDefinition):
        self.image = image
        self.table = table
        if table.codec not in _CODEC_SIZE:
            raise MapModelError(f"Unsupported table codec: {table.codec}")
        self.display_expr = SafeExpression(table.display_math or "X")
        self.inverse_expr = SafeExpression(table.inverse_math) if table.inverse_math else None
        self.row_headers = self._resolve_axis(table.row_axis, table.rows)
        self.column_headers = self._resolve_axis(table.column_axis, table.columns)
        if len(self.row_headers) != table.rows:
            raise MapModelError("Row axis length does not match row count")
        if len(self.column_headers) != table.columns:
            raise MapModelError("Column axis length does not match column count")
        # Bounds-check the complete table immediately.
        image._check(table.address, table.rows * table.columns * _CODEC_SIZE[table.codec])

    def _resolve_axis(self, axis: AxisDefinition, expected_count: int) -> list[float]:
        if axis.mode == "static":
            values = list(axis.values)
            if not values:
                values = [float(i) for i in range(expected_count)]
            return [float(v) for v in values]
        if axis.mode != "linked":
            raise MapModelError(f"Unsupported axis mode: {axis.mode}")
        if axis.address is None:
            raise MapModelError("Linked axis is missing an address")
        if axis.codec not in _CODEC_SIZE:
            raise MapModelError(f"Unsupported axis codec: {axis.codec}")
        count = axis.count or expected_count
        expr = SafeExpression(axis.math or "X")
        size = _CODEC_SIZE[axis.codec]
        out: list[float] = []
        for index in range(count):
            raw = self.image.read_codec(axis.address + index * size, axis.codec)
            out.append(expr.evaluate(raw))
        return out

    def _address(self, row: int, column: int) -> int:
        if not (0 <= row < self.table.rows and 0 <= column < self.table.columns):
            raise MapModelError(f"Cell ({row}, {column}) outside table")
        index = row * self.table.columns + column
        return self.table.address + index * _CODEC_SIZE[self.table.codec]

    def raw_value(self, row: int, column: int) -> int:
        return self.image.read_codec(self._address(row, column), self.table.codec)

    def display_value(self, row: int, column: int) -> float:
        return self.display_expr.evaluate(self.raw_value(row, column))

    def values(self) -> list[list[float]]:
        return [
            [self.display_value(r, c) for c in range(self.table.columns)]
            for r in range(self.table.rows)
        ]

    def _encode_display(self, value: float) -> int:
        if self.table.minimum is not None and value < self.table.minimum:
            raise MapModelError(f"Value {value} is below table minimum {self.table.minimum}")
        if self.table.maximum is not None and value > self.table.maximum:
            raise MapModelError(f"Value {value} is above table maximum {self.table.maximum}")
        if self.inverse_expr is None:
            raise MapModelError("Table has no supported inverse math; it is read-only")
        raw_float = self.inverse_expr.evaluate(value)
        raw = int(round(raw_float))
        low, high = _CODEC_RANGE[self.table.codec]
        if raw < low or raw > high:
            raise MapModelError(f"Raw value {raw} exceeds {self.table.codec} range {low}..{high}")
        return raw

    def set_display_value(self, row: int, column: int, value: float) -> MapEdit:
        address = self._address(row, column)
        old_raw = self.image.read_codec(address, self.table.codec)
        new_raw = self._encode_display(float(value))
        self.image.write_codec(address, self.table.codec, new_raw)
        return MapEdit((CellChange(row, column, old_raw, new_raw),))

    def apply_formula(self, cells: Iterable[tuple[int, int]], formula: str) -> MapEdit:
        targets = list(dict.fromkeys(cells))
        if not targets:
            raise MapModelError("No cells selected")

        planned: list[CellChange] = []
        # Pre-compute every value before touching the image to guarantee atomicity.
        for row, column in targets:
            current = self.display_value(row, column)
            try:
                display = apply_quick_formula(current, formula)
            except MathExpressionError as exc:
                raise MapModelError(str(exc)) from exc
            new_raw = self._encode_display(display)
            old_raw = self.raw_value(row, column)
            planned.append(CellChange(row, column, old_raw, new_raw))

        for change in planned:
            self.image.write_codec(
                self._address(change.row, change.column), self.table.codec, change.new_raw
            )
        return MapEdit(tuple(planned))

    def undo_edit(self, edit: MapEdit) -> None:
        for change in edit.changes:
            self.image.write_codec(
                self._address(change.row, change.column), self.table.codec, change.old_raw
            )

    def redo_edit(self, edit: MapEdit) -> None:
        for change in edit.changes:
            self.image.write_codec(
                self._address(change.row, change.column), self.table.codec, change.new_raw
            )

    def nearest_cell(self, rpm: float, tps: float) -> tuple[int, int]:
        if not self.row_headers or not self.column_headers:
            raise MapModelError("Map axes are empty")
        row = min(range(len(self.row_headers)), key=lambda i: abs(self.row_headers[i] - rpm))
        column = min(range(len(self.column_headers)), key=lambda i: abs(self.column_headers[i] - tps))
        return row, column
