from __future__ import annotations
from dataclasses import dataclass
import time
from .base_interface import HardwareInterface,LiveSample
@dataclass
class FrameEntry:
    timestamp:float; direction:str; data:bytes
@dataclass
class InitCandidate:
    name:str; baudrate:int
class SerialInterface(HardwareInterface):
    def __init__(self): self.ser=None; self.port=None; self.frame_log=[]
    @staticmethod
    def list_ports():
        from serial.tools import list_ports
        return list(list_ports.comports())
    def connect(self,port=None,baudrate=10400,**kwargs):
        import serial
        if not port: raise RuntimeError("Select a COM port")
        self.ser=serial.Serial(port=port,baudrate=baudrate,timeout=.25,write_timeout=.5); self.port=port
    def disconnect(self):
        if self.ser:
            try:self.ser.close()
            finally:self.ser=None
    def is_connected(self): return bool(self.ser and self.ser.is_open)
    def initialize_kwp_profile(self,profile):
        if not self.is_connected(): raise RuntimeError("Serial interface is not connected")
        return InitCandidate("Generic K-Line session",profile.baudrate), b""
    def read_live_sample(self): raise RuntimeError("Live PID mapping requires an ECU-specific profile")
    def prepare_flash(self,payload): raise RuntimeError("Generic Serial K-Line profile is read-only; ECU-specific flashing is intentionally disabled")
