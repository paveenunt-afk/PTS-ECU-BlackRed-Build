from __future__ import annotations

import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from hardware.base_interface import HardwareInterface


class LoggerWorker(QObject):
    sample_received = pyqtSignal(object)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(self, backend: HardwareInterface, poll_interval: float = 0.05):
        super().__init__()
        self.backend = backend
        self.poll_interval = max(0.005, float(poll_interval))
        self._stop_event = threading.Event()

    @pyqtSlot()
    def run(self) -> None:
        self._stop_event.clear()
        self.status_changed.emit("Logging")
        try:
            self.backend.start_logging()
            while not self._stop_event.is_set():
                started = time.monotonic()
                sample = self.backend.read_live_sample()
                self.sample_received.emit(sample)
                delay = self.poll_interval - (time.monotonic() - started)
                if delay > 0:
                    self._stop_event.wait(delay)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            try:
                self.backend.stop_logging()
            except Exception as exc:
                self.error_occurred.emit(str(exc))
            self.status_changed.emit("Stopped")
            self.stopped.emit()

    def request_stop(self) -> None:
        self._stop_event.set()
