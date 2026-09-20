from __future__ import annotations
import random,math,time
from .base_interface import HardwareInterface,LiveSample
class MockInterface(HardwareInterface):
    def __init__(self,seed=7): self.r=random.Random(seed); self.connected=False; self.t0=time.monotonic(); self._written=None
    def connect(self,**kwargs): self.connected=True
    def disconnect(self): self.connected=False
    def is_connected(self): return self.connected
    def read_vehicle_info(self): return {"interface":"Mock","ecu":"PTS Demo ECU","status":"Simulation"}
    def read_live_sample(self):
        if not self.connected: raise RuntimeError("Mock interface is not connected")
        t=time.monotonic()-self.t0; rpm=700+5600*(0.5+0.5*math.sin(t*0.7)); tps=50+45*math.sin(t*0.43)
        return LiveSample(max(0,rpm),max(0,min(100,tps)))
    def prepare_flash(self,payload):
        if not self.connected: raise RuntimeError("Mock interface is not connected")
    def write_image(self,payload,progress_callback=None):
        for p in range(0,101,10):
            if progress_callback: progress_callback(p)
            time.sleep(.01)
        self._written=bytes(payload)
    def verify_image(self,payload): return self._written==bytes(payload)
