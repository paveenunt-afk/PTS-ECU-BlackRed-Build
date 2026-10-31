@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto nopython
py -3 -m pip install pyinstaller > build_log.txt 2>&1
if errorlevel 1 goto fail
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name PTS_Studio_3 --paths . --add-data "README_TH.txt;." app.pyw >> build_log.txt 2>&1
if errorlevel 1 goto fail
echo สร้างสำเร็จ: dist\PTS_Studio_3.exe
echo สามารถคัดลอก EXE ไปใช้บน Windows สถาปัตยกรรมเดียวกับเครื่องที่สร้างได้
start "" "%~dp0dist"
pause
exit /b 0
:nopython
echo ต้องติดตั้ง Python 3 พร้อม Python Launcher และ Tcl/Tk ก่อนสร้าง EXE
pause
exit /b 1
:fail
echo สร้างไม่สำเร็จ เปิด build_log.txt เพื่อดูรายละเอียด
pause
exit /b 1
