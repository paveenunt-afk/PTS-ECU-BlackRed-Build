from __future__ import annotations

import threading

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from core.bin_engine import BinImage
from hardware.base_interface import HardwareInterface
from hardware.ecu_profiles import EcuProfile, validate_flash_preconditions


class FlashWorker(QObject):
    progress = pyqtSignal(int, str)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, backend: HardwareInterface, image: BinImage, profile: EcuProfile):
        super().__init__()
        self.backend = backend
        self.image = image
        self.profile = profile
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.status_changed.emit("Validating flash preconditions")
            check = validate_flash_preconditions(self.image, self.profile, self.backend)
            if not check.ok:
                raise RuntimeError("; ".join(check.errors))
            if self._cancel.is_set():
                self.finished.emit(False)
                return
            payload = self.image.to_bytes()
            self.progress.emit(5, "Preparing programming session")
            self.backend.prepare_flash(payload)
            if self._cancel.is_set():
                self.finished.emit(False)
                return

            self.progress.emit(10, "Writing image")
            def report(value: int):
                self.progress.emit(10 + int(max(0, min(100, value)) * 0.75), "Writing image")
            self.backend.write_image(payload, progress_callback=report)

            # Cancellation is intentionally checked only at the safe boundary after write.
            if self._cancel.is_set():
                self.status_changed.emit("Cancel requested; write completed, verification skipped")
                self.finished.emit(False)
                return
            self.progress.emit(90, "Verifying image")
            if not self.backend.verify_image(payload):
                raise RuntimeError("Verification failed")
            self.progress.emit(100, "Flash verified")
            self.finished.emit(True)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            self.finished.emit(False)
