# PTS ECU Tuning, Data Logger & Software Flash

โปรแกรมเดสก์ท็อป Python/PyQt5 สำหรับแก้ไขไฟล์ ECU BIN, อ่าน XDF/XML, แสดงตารางจูนแบบ heat-map, Data Logger แบบ real-time และเชื่อมต่อ COM/Serial โดยแยก hardware backend ออกจาก UI ชัดเจน

## จุดเด่นของรุ่นนี้

- Dark/Cyan Neon UI แบบสปอร์ต 3 แท็บ: Welcome, Tuning Grid, Datalog Graph
- เปิด/บันทึก `.bin` ด้วย binary mode และรองรับ `B`, `>H`, `<H`
- XDF/XML parser รองรับ table/address/math/inverse math และ Static/Linked Axis
- เลือกหลายช่องแบบ `ContiguousSelection` แล้วใช้ Quick Math เช่น `+1.5`, `-2`, `*1.1`, `/1.05`
- Heat-map ไล่สีตามค่าจูน และ Live Cell Tracing จาก RPM/TPS
- pyqtgraph real-time trace แกน ENGINE RPM 0–13,000
- Mock Mode ทำงานได้โดยไม่ต้องต่อรถ: RPM/TPS เคลื่อนไหว, graph วิ่ง, cell tracing ทำงาน
- COM auto-detect/ranking สำหรับ FTDI, CH340, CP210x และ USB-Serial ที่พบผ่าน pySerial
- Serial TX/RX frame log แบบจำกัดขนาด
- K-Line/KWP adapter แบบ profile-driven ที่เก็บ wake/session candidate ได้โดยไม่ถือว่าใช้ได้กับ ECU ทุกตัว
- Flash guard: unknown/generic K-Line เป็น read-only; write เปิดเฉพาะ profile ที่ประกาศ writable และผ่าน size/range/interface validation
- มี Demo BIN/XDF 64-byte เปิดให้โดยอัตโนมัติ

## ติดตั้งบน Windows

แนะนำ **Python 3.11 หรือ 3.12 แบบ 64-bit** (ขั้นต่ำ Python 3.10)

### วิธีง่ายที่สุด

1. แตก ZIP ออกมาก่อน อย่ารันจากใน WinRAR/7-Zip
2. ดับเบิลคลิก `run_pts.bat`
3. ครั้งแรก launcher จะสร้าง `.venv`, ติดตั้ง `PyQt5`, `pyqtgraph`, `pyserial` และเปิดโปรแกรมด้วย Python ใน `.venv` ตัวเดียวกันโดยอัตโนมัติ

ถ้าต้องการติดตั้งแยก ให้ดับเบิลคลิก `setup_windows.bat` ก่อน แล้วจึงเปิด `run_pts.bat`

Runtime dependencies อยู่ใน `requirements.txt`; package สำหรับ test ถูกแยกไป `requirements-dev.txt` เพื่อไม่เพิ่มภาระในการติดตั้งสำหรับผู้ใช้ทั่วไป

หากติดตั้ง PyQt5 ไม่ผ่านและใช้ Python รุ่นใหม่มาก ให้ติดตั้ง Python 3.11/3.12 จาก python.org แล้วรัน `setup_windows.bat` อีกครั้ง

### แก้ปัญหา Qt platform plugin `windows`

รุ่น QT FIX จะตั้งตำแหน่ง `qwindows.dll` จาก `.venv` โดยตรงก่อนเปิด `QApplication` และล้าง `QT_PLUGIN_PATH` ที่อาจตกค้างจาก Qt/Python โปรแกรมอื่น หาก `qwindows.dll` หาย launcher จะลองติดตั้ง PyQt5 ใหม่อัตโนมัติและจะแสดง path ที่ตรวจพบก่อนเริ่มโปรแกรม

หากข้อความเปลี่ยนเป็น **“plugin was found but could not be loaded”** (ต่างจาก “could not find”) ให้ตรวจ Microsoft Visual C++ 2015–2022 Redistributable x64 เพราะกรณีนั้นหมายถึงเจอ `qwindows.dll` แล้วแต่ dependency ของ DLL โหลดไม่ขึ้น

## การใช้งาน Mock Mode

1. เปิด `main.py`
2. โปรแกรมโหลด `demo/demo.bin` และ `demo/demo.xdf` ให้โดยอัตโนมัติ
3. Mock interface จะเชื่อมต่อและเริ่ม logger อัตโนมัติหลังเปิดหน้าต่างเล็กน้อย
4. เปิดแท็บ **Tuning Grid** เพื่อดู Fuel Map 6×8 และ cell ที่วิ่งตาม RPM/TPS
5. ลากเมาส์คลุมหลายช่อง ใส่ Quick Math เช่น `*1.05` แล้วกด **APPLY TO SELECTION**
6. ใช้ **UNDO/REDO** ได้
7. เปิดแท็บ **Datalog Graph** เพื่อดู RPM/TPS trace และใช้ Run/Clear/Play
8. Demo profile อนุญาต Mock Flash เพื่อทดสอบ workflow เท่านั้น โดยไม่มีการส่งข้อมูลไป ECU จริง

## การใช้ Serial / K-Line จริง

เลือก **Serial K-Line** แล้วกด Refresh เพื่อค้นหา COM Port จากนั้น Connect จะเปิดพอร์ตที่ 10,400 baud ตาม profile เริ่มต้น

> **คำเตือนด้านฮาร์ดแวร์:** USB-to-TTL เช่น FTDI/CH340 ไม่ได้หมายความว่าเป็น K-Line 12 V interface โดยตรง ควรใช้ automotive K-Line transceiver/interface ที่ออกแบบให้รับระดับแรงดันและสภาวะไฟฟ้าของรถก่อนต่อ ECU จริง

ไฟล์ `hardware/kwp2000.py` รองรับ profile-defined initialization candidates รวมถึง candidate ที่ผู้ใช้ให้มา:

- Wake: `FE 04 72 8C`
- Session: `72 05 00 F0 99`
- Baud: `10400`
- Low/High timing metadata: `70 ms / 120 ms`

ชุดนี้ถูกเก็บไว้ใน **Generic K-Line (Read Only)** เพื่อการพัฒนา/วิเคราะห์ และ **ไม่ได้ประกาศว่าใช้ได้กับ Honda ECU ทุกกล่อง** เพราะ session, security access, memory layout, live-data request, erase/write routine และ checksum แตกต่างกันตาม ECU/interface

## เพิ่ม ECU Profile ที่ตรวจสอบแล้ว

เพิ่ม `EcuProfile` ใน `hardware/ecu_profiles.py` โดยกำหนดอย่างน้อย:

- `profile_id`
- `ecu_family`
- `interface_type`
- `baudrate`
- initialization candidate ที่ยืนยันกับ ECU รุ่นนั้น
- `expected_sizes`
- `allowed_read_ranges`
- `allowed_write_ranges`
- checksum/verification strategy
- ตั้ง `writable=True` เฉพาะหลังทดสอบ read/session/write/verify กับ ECU และ interface เป้าหมายแล้ว

Generic/unknown profile ถูกล็อก read-only โดยตั้งใจ

## โครงสร้างหลัก

```text
core/       BIN, XDF, safe math, map model, session state
hardware/   backend interface, Mock, Serial, KWP, ECU profiles
workers/    logger/flash QObject workers สำหรับ QThread
ui/         main window, pages, tuning grid, serial console
demo/       demo.bin + demo.xdf
assets/     QSS theme
```

## ทดสอบ

```bat
python -m pip install pytest pytest-qt
pytest -q
```

บนเครื่องที่มี PyQt5 + pyqtgraph จะรัน UI smoke tests เพิ่มด้วย ถ้าไม่มี Qt tests ส่วนนั้นจะถูก skip แต่ core tests ยังรันได้

## ขอบเขตของรุ่นแรก

รุ่นนี้พร้อมใช้งานเป็น BIN/XDF editor, Mock ECU data logger, COM transport/diagnostic frame layer และ framework สำหรับ ECU profiles การเขียน ECU จริงไม่ได้เปิดแบบ “ทุกกล่องอัตโนมัติ” เพราะการทำเช่นนั้นโดยไม่รู้ memory map/security/checksum ของ ECU เป้าหมายไม่สามารถรับรองความถูกต้องได้ โปรแกรมจึงบังคับ profile validation ก่อน write เสมอ

## v4 XDF compatibility fix

The XDF loader now reads XML from raw bytes so XML BOM/declarations (including UTF-16) are honored by the XML parser. It also supports the common TunerPro 1.50/1.60 layout where table payload metadata (`mmedaddress`, row/column counts, units and table math) is stored under `XDFAXIS id="z"`.
