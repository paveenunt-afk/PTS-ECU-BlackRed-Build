from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from qt_runtime import QtRuntimeError, configure_qt_runtime

try:
    configure_qt_runtime()
except QtRuntimeError as exc:
    print(f"[PTS ECU] Qt runtime error: {exc}", file=sys.stderr)
    raise

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def configure_logging() -> None:
    log_dir = Path.home() / ".pts_ecu_suite"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "pts_ecu_suite.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def load_theme(app: QApplication) -> None:
    qss = Path(__file__).resolve().parent / "assets" / "theme.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))


def main() -> int:
    configure_logging()
    # Must be selected before QApplication is constructed.
    QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    app = QApplication(sys.argv)
    app.setApplicationName("PTS ECU Tuning Suite")
    app.setOrganizationName("PTS")
    load_theme(app)
    window = MainWindow(auto_start_mock=True)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
