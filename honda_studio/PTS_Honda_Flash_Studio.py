"""PTS Honda Flash Studio: independent file and interface inspection UI.

The supplied Honda Flash binary is not used or executed. ECU flash transport
is not implemented; this application never issues read/write ECU commands.
"""

import hashlib
import json
import re
import tkinter as tk
import ctypes
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

TARGET_PART = "30400-K3MH-T71-TH-01"
TARGET_SIZE = 262144
REFERENCE_HASH = "6d480eb5b1a4411f0b1f1d15e7292209047de48c9b665885e7da47762850b9eb"

# ECU identification values supplied by the user. These are catalog metadata,
# not protocol commands and not evidence that a particular ECU can be flashed.
CATALOG_TEXT = """0101610D01|K03-T61|เวฟ 110i|4000|9FEF|48|KEIHIN
0100CE0D01|KWW-642|เวฟ 110i|4000|9FEF|48|KEIHIN
0100CE0D02|KWW-643|เวฟ 110i|4000|9FEF|48|KEIHIN
01010E0D01|KYZ-T03|เวฟ 110i|4000|9FEF|48|KEIHIN
0101350101|K26-931|MSX 125|4000|9FEF|48|KEIHIN
0101350501|K26-911|MSX 125|4000|9FEF|48|KEIHIN
0101350D01|K26-901|MSX 125|4000|9FEF|48|KEIHIN
0100DF0D02|KVB-S53|Click 110i|4000|9FEF|48|KEIHIN
0101180D01|K16-901|สกุ๊ปปี้ i|4000|9FEF|48|KEIHIN
0101850D01|K16-B01|สกุ๊ปปี้ i|4000|9FEF|48|KEIHIN
0101270D01|K20-901|ซูมเมอร์-X|4000|9FEF|48|KEIHIN
0100C50D02|KPP-T03|CBR 150R|0|DFEF|56|KEIHIN
0100B80D01|KYJ-901|CBR 250R|0|DFEF|56|KEIHIN
0100B20D01|KWW-601|เวฟ 110i|0|7FEF|56|KEIHIN
0101110F01|KPP-602|CBR 150|0|DFEF|56|KEIHIN
0100DB0D01|KYL-T01|เวฟ 125 บังลม|0|7FEF|56|KEIHIN
0101880D01|K03-H01|เวฟ 110i|8000|0|64|KEIHIN
01034C0D01|K58-TC2|เวฟ 110i|8000|0|64|KEIHIN
0102B90D01|K58 T81|เวฟ 110i|8000|0|64|KEIHIN
01040F0D01|K2J-T01|เวฟ 110i|8000|0|64|KEIHIN
0105550D01|K2J TH1|เวฟ 110i|8000|0|64|KEIHIN
01047B0D01|K3F-T01|เวฟ 125 ปลาวาฬ|8000|0|64|KEIHIN
0103FA0D01|K1M-T01|ดรีม 110i|8000|0|64|KEIHIN
0102580D01|K73-T32|เวฟ 125 ปลาวาฬ|8000|0|64|KEIHIN
01033E0D01|K73-T61|เวฟ 125 ปลาวาฬ|8000|0|64|KEIHIN
01034F1801|K73-TC2|เวฟ 125 ปลาวาฬ|8000|0|64|KEIHIN
0102B50D01|K76-T62|ดรีม 110i|8000|0|64|KEIHIN
0101BA0D01|KZV-A61|ดรีม 110i|8000|0|64|KEIHIN
0101B30D01|KYZ-T41|เวฟ 125 ปลาวาฬ|8000|0|64|KEIHIN
0103250F01|K54-NA1|CBR 150|8000|0|64|KEIHIN
0101C60D01|K16-B61|สกุ๊ปปี้ i|8000|0|64|KEIHIN
0103130F01|K15-601|CB 150R|8000|0|64|KEIHIN
0102130D01|K26-B02|MSX 125 SF|8000|0|64|KEIHIN
0102130501|K26-B13|MSX 125|8000|0|64|KEIHIN
0103250D01|K45-TA1|CBR 150R|8000|0|64|KEIHIN
0102A00D01|K94-T02|CB 150R|8000|0|96|KEIHIN
0100C31501|KZZ-J01|CRF 250|8000|0|96|KEIHIN
0102B70D02|K0A-T01|CB 650R|8000|0|96|KEIHIN
0102CA0501|K0F-A01|Monkey 125|8000|0|96|KEIHIN
0102CA0D01|K0F-T01|Monkey 125|8000|0|96|KEIHIN
01041F0D01|K0F-T61|Monkey 125|8000|0|96|KEIHIN
01030E0D01|K0G-902|ดรีม 125i|8000|0|96|KEIHIN
0103F90D01|K2F-T02|CT 125 LED|8000|0|96|KEIHIN
0104070D01|K1T-T01|CRF 300L|8000|0|96|KEIHIN
0104070501|K1T-A11|CRF 300L|8000|0|96|KEIHIN
0102360F01|KZZ-L41|CRF 250|8000|0|96|KEIHIN
0102570601|K26-C01|MSX 125|8000|0|96|KEIHIN
0103EB0D01|K26-G01|MSX GROM|8000|0|96|KEIHIN
0102360F11|KZZJ-L41|CRF 250|8000|0|96|KEIHIN
01015B0D01|KZZ-A22|CRF 250|E0000|B000|128|KEIHIN
01011A0D02|KZZ-903|CRF 250L|E0000|B000|128|KEIHIN
01011A0D01|KZZ-902|CRF 250L|E0000|B000|128|KEIHIN
0101740D02|KZZ-914|CRF 250L|E0000|B000|128|KEIHIN
01019E0D01|K33-951|CB 300F|E0000|E0000|128|KEIHIN
01052A0D01|K3MF-T01|จีออโน่ 125|auto|auto|256|SHINDENGEN
0104780D01|K2TA-T02|หลีด 125 4v|auto|auto|256|SHINDENGEN
0101FF0D01|K20J-T21|ซูมเมอร์ X|auto|auto|256|SHINDENGEN
0104F20D01|K2F-T91|สกุ๊ปปี้ i|auto|auto|256|SHINDENGEN
0101830401|MGP-A92|CBR 1000 RR|auto|auto|256|SHINDENGEN
01031A0501|MKN-L32|CBR 650 R ABS|auto|auto|256|SHINDENGEN
01031A1801|MKN-U11|CBR 650 R|auto|auto|256|SHINDENGEN
01030A0D01|K60S-T71|Click 125|auto|auto|384|SHINDENGEN
0103070D01|K59K-T11|Click 150|auto|auto|384|SHINDENGEN
01037C0D01|K0WF-T01|ADV 150|auto|auto|384|SHINDENGEN
0101D00D01|K60F-T01|Click 125|auto|auto|384|SHINDENGEN
0103960D01|K12M-J61|หลีด 125 2v|auto|auto|384|SHINDENGEN
01046D0D01|K2SF-T01|Click 160|auto|auto|384|SHINDENGEN
01048E0D01|K0WM-TA1|ADV 160|auto|auto|384|SHINDENGEN
01048D0D01|K0WL-T01|ADV 160|auto|auto|384|SHINDENGEN
0101990D01|K36F-T01|PCX 150|auto|auto|384|SHINDENGEN
0103D00D01|K1ZF-T01|PCX 160|auto|auto|384|SHINDENGEN
0103CF0D01|K1ZF-T11|PCX 160 ABS|auto|auto|384|SHINDENGEN
0102180D01|K36S-T31|PCX 150|auto|auto|384|SHINDENGEN
0102990D01|K97F-T01|PCX 150|auto|auto|384|SHINDENGEN
0105050D01|K1ZP-T51|PCX 160|auto|auto|384|SHINDENGEN
0105040D01|K1ZP-T71|PCX 160 ABS|auto|auto|384|SHINDENGEN
0105950D01|K2TG-T21|หลีด 125 4v|auto|auto|384|SHINDENGEN
0105B30D01|K1ZT-TC1|PCX 160|auto|auto|384|SHINDENGEN
0105B40D01|K1ZT-TF1|PCX 160|auto|auto|384|SHINDENGEN
0106270D01|K3F-T41|เวฟ 125 ปลาวาฬ|8000|0|64|KEIHIN
0106280D01|K3F-T61|เวฟ 125 ปลาวาฬ|8000|0|96|KEIHIN
01062C0D01|K2J-TQ1|Wave 110i 2026|8000|0|64|KEIHIN
0106A70D01|K3MH-T71|GIORNO 125 2026|auto|auto|256|SHINDENGEN"""
CATALOG = [dict(zip(("software_id", "family", "model", "start", "end", "size_kib", "maker"),
                    line.split("|"))) for line in CATALOG_TEXT.splitlines()]
THAI_KEYS = {
    "path": "ไฟล์", "size_bytes": "ขนาดไฟล์ (ไบต์)", "sha256": "รหัสตรวจสอบ SHA-256",
    "same_as_supplied_file": "ตรงกับไฟล์อ้างอิงที่ส่งมา", "markers": "ข้อความระบุซอฟต์แวร์",
    "ecu_identity": "หมายเลขกล่อง", "original": "ไฟล์ต้นฉบับ", "candidate": "ไฟล์เปรียบเทียบ",
    "same_bytes": "ข้อมูลเหมือนกันทุกไบต์", "different_bytes": "จำนวนไบต์ที่ต่างกัน",
    "flash_compatibility": "ความเข้ากันได้ในการอัดไฟล์", "source": "แหล่งบันทึก",
    "matches": "รหัสที่พบ", "status": "สถานะ", "note": "หมายเหตุ",
    "flash_read": "ดูดไฟล์จากกล่อง", "flash_write": "อัดไฟล์ลงกล่อง",
    "software_id": "รหัสซอฟต์แวร์", "family": "รหัสตระกูลกล่อง",
    "model": "รุ่นรถ", "size_kib": "ขนาดไฟล์ (กิโลไบต์)",
    "start": "ค่าเริ่มต้นตามตาราง", "end": "ค่าสิ้นสุดตามตาราง", "maker": "ผู้ผลิตกล่อง",
}


def thai_report(value):
    if isinstance(value, dict):
        return {THAI_KEYS.get(key, key): thai_report(item) for key, item in value.items()}
    if isinstance(value, list):
        return [thai_report(item) for item in value]
    if value == "NOT_IMPLEMENTED":
        return "ยังไม่มีฟังก์ชันนี้"
    if value == "UNKNOWN: การเทียบไฟล์ไม่ยืนยันว่าอัดลง ECU ได้":
        return "ยังไม่ทราบ: การเทียบไฟล์ไม่ยืนยันว่าอัดลงกล่องได้"
    return value


def identify_from_log(raw_text):
    """Find an exact 5-byte software ID in a diagnostic trace, if present."""
    hex_runs = [run.upper() for run in re.findall(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{10,}(?![0-9A-Fa-f])", raw_text)]
    matches = [item for item in CATALOG if any(item["software_id"] in run for run in hex_runs)]
    return matches


def detect_ftdi_d2xx():
    """Ask FTDI's installed D2XX driver how many devices are available."""
    if sys.platform != "win32":
        raise RuntimeError("FTDI D2XX ใช้ได้บน Windows ในโปรแกรมนี้")
    dll = ctypes.WinDLL("ftd2xx.dll")
    dll.FT_CreateDeviceInfoList.argtypes = [ctypes.POINTER(ctypes.c_ulong)]
    dll.FT_CreateDeviceInfoList.restype = ctypes.c_ulong
    count = ctypes.c_ulong()
    status = dll.FT_CreateDeviceInfoList(ctypes.byref(count))
    if status:
        raise RuntimeError(f"FTDI D2XX error {status}")
    return count.value


def detect_openport_j2534():
    """Open and immediately close the installed Openport 2.0 J2534 device."""
    if sys.platform != "win32":
        raise RuntimeError("Openport J2534 ใช้ได้บน Windows ในโปรแกรมนี้")
    dll = ctypes.WinDLL("op20pt32.dll")
    dll.PassThruOpen.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    dll.PassThruOpen.restype = ctypes.c_long
    dll.PassThruClose.argtypes = [ctypes.c_ulong]
    dll.PassThruClose.restype = ctypes.c_long
    device = ctypes.c_ulong()
    status = dll.PassThruOpen(None, ctypes.byref(device))
    if status:
        raise RuntimeError(f"Openport J2534 error {status}")
    try:
        return device.value
    finally:
        dll.PassThruClose(device)


def inspect_image(path):
    data = Path(path).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    markers = {}
    for text in (b"SH850T01R100_PV103", b"DH850T01xxxxxxV211", b"ECM -EngineControl"):
        pos = data.find(text)
        if pos >= 0:
            markers[text.decode("ascii")] = f"0x{pos:X}"
    return {"path": str(path), "size_bytes": len(data), "sha256": sha,
            "same_as_supplied_file": len(data) == TARGET_SIZE and sha == REFERENCE_HASH,
            "markers": markers, "ecu_identity": "ยังไม่ได้ยืนยันจากกล่องจริง"}


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PTS ฮอนด้าแฟลช | ตรวจไฟล์และอุปกรณ์")
        self.geometry("960x650")
        self.configure(bg="#111216")
        self.first = None
        self.second = None
        bar = tk.Frame(self, bg="#9f1624", height=62)
        bar.pack(fill="x")
        tk.Label(bar, text="PTS  |  ฮอนด้าแฟลช", fg="white", bg="#9f1624",
                 font=("Segoe UI", 19, "bold")).pack(side="left", padx=22, pady=12)
        tk.Label(self, text="รหัสไฟล์อ้างอิง: " + TARGET_PART + "  •  ขนาด 256 กิโลไบต์",
                 bg="#111216", fg="#eeeeee", font=("Segoe UI", 12)).pack(anchor="w", padx=20, pady=(16, 6))
        tk.Label(self, text="สถานะกล่อง: ยังไม่เชื่อมต่อ  |  ดูดไฟล์: ยังไม่มี  |  อัดไฟล์: ยังไม่มี",
                 bg="#111216", fg="#ff7777", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20)
        controls = tk.Frame(self, bg="#111216")
        controls.pack(fill="x", padx=20, pady=18)
        for label, fn in (("รายการรหัสกล่อง", self.catalog),
                          ("เปิดไฟล์กล่อง", self.open_first), ("เปรียบเทียบไฟล์", self.open_second),
                          ("อ่านรหัสจากบันทึก", self.open_log),
                          ("ค้นหาพอร์ต", self.ports), ("บันทึกรายงาน", self.save_report)):
            tk.Button(controls, text=label, command=fn, bg="#b51c2b", fg="white",
                      activebackground="#d52b3a", relief="flat", font=("Segoe UI", 11),
                      padx=13, pady=9).pack(side="left", padx=(0, 9))
        interfaces = tk.Frame(self, bg="#111216")
        interfaces.pack(fill="x", padx=20, pady=(0, 12))
        for label, fn in (("ตรวจสาย K-Line FT232RL", self.ftdi),
                          ("ตรวจสาย CAN Openport 2.0", self.openport)):
            tk.Button(interfaces, text=label, command=fn, bg="#343741", fg="white",
                      relief="flat", font=("Segoe UI", 10), padx=10, pady=7).pack(side="left", padx=(0, 9))
        self.output = tk.Text(self, bg="#1c1e24", fg="#eeeeee", insertbackground="white",
                              font=("Consolas", 11), wrap="word", relief="flat")
        self.output.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.show("เปิดไฟล์กล่องเพื่อดูขนาด รหัสตรวจสอบ SHA-256 และข้อความระบุซอฟต์แวร์\n"
                  "การค้นหาพอร์ตแสดงรายการอุปกรณ์ ยังไม่ส่งข้อมูลไปยังกล่อง")

    def show(self, text):
        self.output.delete("1.0", "end")
        self.output.insert("end", text)

    def catalog(self):
        window = tk.Toplevel(self)
        window.title("ตารางรหัส ECU ที่ผู้ใช้ให้")
        window.geometry("1050x560")
        window.configure(bg="#111216")
        query = tk.StringVar()
        tk.Label(window, text="ค้นหารหัสซอฟต์แวร์ รุ่นรถ หรือผู้ผลิต", bg="#111216",
                 fg="white", font=("Segoe UI", 11)).pack(anchor="w", padx=14, pady=(12, 4))
        entry = tk.Entry(window, textvariable=query, font=("Segoe UI", 12))
        entry.pack(fill="x", padx=14, pady=(0, 10))
        columns = ("software_id", "family", "model", "start", "end", "size_kib", "maker")
        table = ttk.Treeview(window, columns=columns, show="headings")
        for key, width in zip(columns, (140, 135, 210, 90, 90, 110, 130)):
            table.heading(key, text=THAI_KEYS[key])
            table.column(key, width=width, anchor="center")
        scroll = ttk.Scrollbar(window, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        table.pack(fill="both", expand=True, padx=(14, 0), pady=(0, 14))

        def refresh(*_):
            table.delete(*table.get_children())
            term = query.get().strip().casefold()
            for item in CATALOG:
                if term in " ".join(item.values()).casefold():
                    table.insert("", "end", values=tuple(item[key] for key in columns))

        query.trace_add("write", refresh)
        refresh()
        entry.focus_set()

    def open_first(self):
        path = filedialog.askopenfilename(title="เลือกไฟล์กล่อง", filetypes=[("ไฟล์ BIN", "*.bin"), ("ทุกไฟล์", "*")])
        if path:
            try:
                self.first = inspect_image(path)
                self.second = None
                self.show(json.dumps(thai_report(self.first), ensure_ascii=False, indent=2))
            except OSError as exc:
                messagebox.showerror("อ่านไฟล์ไม่สำเร็จ", str(exc))

    def open_second(self):
        if not self.first:
            messagebox.showinfo("เลือกไฟล์", "เปิดไฟล์กล่องฉบับแรกก่อน")
            return
        path = filedialog.askopenfilename(title="เลือกไฟล์เปรียบเทียบ")
        if path:
            try:
                self.second = inspect_image(path)
                a = Path(self.first["path"]).read_bytes()
                b = Path(path).read_bytes()
                changes = sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))
                report = {"original": self.first, "candidate": self.second,
                          "same_bytes": a == b, "different_bytes": changes,
                          "flash_compatibility": "UNKNOWN: การเทียบไฟล์ไม่ยืนยันว่าอัดลง ECU ได้"}
                self.show(json.dumps(thai_report(report), ensure_ascii=False, indent=2))
            except OSError as exc:
                messagebox.showerror("เปรียบเทียบไม่สำเร็จ", str(exc))

    def ports(self):
        try:
            from serial.tools import list_ports
            ports = list(list_ports.comports())
            self.show("พอร์ตที่พบ (ยังไม่ได้เชื่อมต่อกล่อง):\n" +
                      ("\n".join(f"{p.device} | {p.description} | VID:PID {p.vid}:{p.pid}" for p in ports)
                       if ports else "ไม่พบพอร์ต COM"))
        except ImportError:
            self.show("ต้องติดตั้ง pyserial เพื่อดูรายการพอร์ต COM")

    def open_log(self):
        path = filedialog.askopenfilename(title="เลือกบันทึกคำตอบกล่อง", filetypes=[("บันทึก", "*.txt *.log *.jsonl"), ("ทุกไฟล์", "*")])
        if path:
            try:
                matches = identify_from_log(Path(path).read_text(encoding="utf-8"))
                self.show(json.dumps(thai_report({"source": path, "matches": matches,
                    "status": "พบรหัสตรงตารางผู้ใช้" if matches else "ไม่พบรหัสตรงตาราง",
                    "note": "รหัสนี้ต้องมาจากคำตอบกล่อง ไม่ใช่ข้อมูลที่ส่งออกหรือสัญญาณสะท้อน",
                    "flash_read": "NOT_IMPLEMENTED", "flash_write": "NOT_IMPLEMENTED"}),
                    ensure_ascii=False, indent=2))
            except (OSError, UnicodeError) as exc:
                messagebox.showerror("อ่านบันทึกไม่สำเร็จ", str(exc))

    def ftdi(self):
        try:
            count = detect_ftdi_d2xx()
            self.show(f"สาย K-Line FT232RL: พบอุปกรณ์ {count} ตัว\nยังไม่ได้เชื่อมต่อกล่องหรือส่งคำสั่ง")
        except (OSError, RuntimeError, AttributeError) as exc:
            self.show(f"FTDI D2XX: {exc}")

    def openport(self):
        try:
            device = detect_openport_j2534()
            self.show(f"สาย CAN Openport 2.0: เปิดและปิดอุปกรณ์ได้ (รหัส {device})\nยังไม่ได้เชื่อมต่อช่อง CAN หรือส่งคำสั่งกล่อง")
        except (OSError, RuntimeError, AttributeError) as exc:
            self.show(f"Openport J2534: {exc}")

    def save_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            try:
                Path(path).write_text(self.output.get("1.0", "end"), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("บันทึกไม่สำเร็จ", str(exc))


if __name__ == "__main__":
    Studio().mainloop()
