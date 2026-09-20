PTS ECU BlackRed v10 - UI + Thai Voice Fast

แก้ตัว Build แล้ว: รุ่นก่อนหน้าอ้างถึงโฟลเดอร์ demo ที่ไม่มีอยู่ ทำให้ PyInstaller หยุดก่อนสร้าง dist\*.exe

วิธีสร้างตัวติดตั้งไฟล์เดียว:
1. แตก ZIP ทั้งหมดลงโฟลเดอร์ปกติ (อย่ารันจากใน WinRAR)
2. ดับเบิลคลิก build_installer.bat
3. รอจนขึ้น SUCCESS
4. ไฟล์สุดท้าย: PTS_ECU_BlackRed_v10_Setup.exe

ตัว Build จะตรวจ Python, สร้าง virtual environment, ติดตั้ง dependencies, สร้าง EXE ด้วย PyInstaller และเรียก NSIS อัตโนมัติ
ถ้าไม่สำเร็จ จะสร้าง build_log.txt ไว้ในโฟลเดอร์เดียวกัน

หมายเหตุ: การแก้ครั้งนี้แก้เฉพาะระบบ Build; ไม่แก้ core/, hardware/, ECU options หรือ logic การใช้งาน
