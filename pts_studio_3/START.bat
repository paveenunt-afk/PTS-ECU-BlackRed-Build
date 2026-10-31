@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo ต้องติดตั้ง Python 3 พร้อม Python Launcher และ Tcl/Tk ก่อน
 echo จากนั้นเปิด START.bat อีกครั้ง
 pause
 exit /b 1
)
py -3 app.pyw
if errorlevel 1 (
 echo เปิด PTS ไม่สำเร็จ กรุณาตรวจข้อความด้านบน
 pause
 exit /b 1
)
