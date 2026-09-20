# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
datas = []
for folder in ("assets", "demo"):
    p = root / folder
    if p.exists():
        datas.append((str(p), folder))

icon = str(root / "assets" / "pts.ico") if (root / "assets" / "pts.ico").exists() else None

a = Analysis(
    ['main.py'],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=['serial.tools.list_ports'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='PTS_ECU_BlackRed_v10',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, icon=icon,
)
