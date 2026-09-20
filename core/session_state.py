from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.bin_engine import BinImage
from core.xdf_parser import TableDefinition, XdfDocument


@dataclass
class SessionState:
    bin_image: BinImage | None = None
    xdf_document: XdfDocument | None = None
    selected_table: TableDefinition | None = None
    backend_name: str = "Mock"
    ecu_profile: Any = None
    connection_state: str = "Offline"
    logging: bool = False
    flashing: bool = False
    last_folder: str = ""

    @property
    def dirty(self) -> bool:
        return bool(self.bin_image and self.bin_image.dirty)
