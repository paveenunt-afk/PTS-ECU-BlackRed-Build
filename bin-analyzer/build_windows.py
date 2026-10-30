"""Build a genuine Windows x64 EXE locally; never publish or contact an ECU."""
from pathlib import Path
import os
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent

def run(args):
    subprocess.run([str(x) for x in args],cwd=ROOT,check=True)

def main():
    if sys.platform!='win32':raise RuntimeError('Build this EXE on Windows x64')
    env=ROOT/'build-env'
    if not (env/'Scripts/python.exe').exists():venv.EnvBuilder(with_pip=True).create(env)
    py=env/'Scripts/python.exe'
    run([py,'-m','pip','install','pyinstaller>=6,<7','capstone>=5,<6','pylibftdi>=0.23,<0.24'])
    run([py,'windows_main.py','--self-test'])
    args=[py,'-m','PyInstaller','--noconfirm','--clean','--onefile','--console','--noupx','--name','PTS_BIN_Analyzer_v3']
    for path in ['ecu_catalog.tsv','LICENSE','SOURCES.txt','README_TH.txt','FLASH_EXPERIMENT_README_TH.txt']:
        args+=['--add-data',path+';.']
    args+=['--add-data','vendor;vendor','--add-data','roms;roms','--hidden-import','pylibftdi','--collect-all','capstone','windows_main.py']
    run(args)
    exe=ROOT/'dist/PTS_BIN_Analyzer_v3.exe'
    subprocess.run([str(exe),'--self-test'],cwd=ROOT,timeout=90,check=True)
    import hashlib
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    (ROOT/'dist/SHA256.txt').write_text(digest+'  '+exe.name+'\n',encoding='utf-8')
    print('Built and smoke-tested: '+str(exe))
    os.startfile(exe.parent)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Build failed: '+str(exc));raise SystemExit(1)
