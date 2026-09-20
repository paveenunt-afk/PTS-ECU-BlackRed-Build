from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class LiveSample:
    rpm: float
    tps: float

class HardwareInterface(ABC):
    @abstractmethod
    def connect(self, **kwargs): ...
    @abstractmethod
    def disconnect(self): ...
    @abstractmethod
    def is_connected(self)->bool: ...
    def start_logging(self): pass
    def stop_logging(self): pass
    @abstractmethod
    def read_live_sample(self)->LiveSample: ...
    def prepare_flash(self,payload:bytes): raise RuntimeError("Flash not supported by this backend")
    def write_image(self,payload:bytes,progress_callback=None): raise RuntimeError("Flash not supported by this backend")
    def verify_image(self,payload:bytes)->bool: return False
