from __future__ import annotations

from PyQt5.QtWidgets import QPlainTextEdit


class SerialConsole(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(2500)
        self.setPlaceholderText("Serial TX/RX frames will appear here")

    def set_entries(self, entries) -> None:
        lines = []
        for e in entries:
            stamp = f"{e.timestamp:.3f}"
            lines.append(f"{stamp}  {e.direction:>2}  {e.data.hex(' ').upper()}")
        self.setPlainText("\n".join(lines))
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
