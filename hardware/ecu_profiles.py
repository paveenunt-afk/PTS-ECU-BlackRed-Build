from __future__ import annotations
from dataclasses import dataclass,field

@dataclass(frozen=True)
class EcuProfile:
    profile_id:str
    name:str
    baudrate:int=10400
    expected_size:int|None=None
    writable:bool=False
    warnings:tuple[str,...]=()

@dataclass
class ValidationResult:
    ok:bool
    errors:list[str]=field(default_factory=list)
    warnings:list[str]=field(default_factory=list)

def mock_demo_profile(): return EcuProfile("mock-demo-64","Mock Demo 64-byte",10400,64,True)
def generic_kline_read_only_profile(): return EcuProfile("generic-kline-read-only","Generic K-Line (Read Only)",10400,None,False,("Read-only safety profile",))
def builtin_profiles(): return [mock_demo_profile(),generic_kline_read_only_profile()]
def validate_flash_preconditions(image,profile,backend):
    errors=[]; warnings=list(profile.warnings)
    if not backend.is_connected(): errors.append("Interface is not connected")
    if not profile.writable: errors.append("Selected ECU profile is read-only")
    if profile.expected_size is not None and image.size != profile.expected_size: errors.append(f"BIN size {image.size} does not match expected {profile.expected_size}")
    return ValidationResult(not errors,errors,warnings)
