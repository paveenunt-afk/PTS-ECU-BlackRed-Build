"""PTS Honda Flash Studio: independent file and interface inspection UI.

The supplied Honda Flash binary is not used or executed. ECU flash transport
is not implemented; this application never issues read/write ECU commands.
"""

import hashlib
import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

TARGET_PART = "30400-K3MH-T71-TH-01"
TARGET_SIZE = 262144
REFERENCE_HASH = "6d480eb5b1a4411f0b1f1d15e7292209047de48c9b665885e7da47762850b9eb"

# ECU identification values supplied by the user. These are catalog metadata,
# not protocol commands and not evidence that a particular ECU can be flashed.
CATALOG_TEXT = """01052A0D01|K3MF-T01|Giorno 125|256
0106A70D01|K3MH-T71|Giorno 125 2026|256
0104780D01|K2TA-T02|Lead 125 4V|256
0103960D01|K12M-J61|Lead 125 2V|384
0105950D01|K2TG-T21|Lead 125 4V|384
0101990D01|K36F-T01|PCX 150|384
0102180D01|K36S-T31|PCX 150|384
0102990D01|K97F-T01|PCX 150|384
0103D00D01|K1ZF-T01|PCX 160|384
0103CF0D01|K1ZF-T11|PCX 160 ABS|384
0105050D01|K1ZP-T51|PCX 160|384
0105040D01|K1ZP-T71|PCX 160 ABS|384
0105B30D01|K1ZT-TC1|PCX 160|384
0105B40D01|K1ZT-TF1|PCX 160|384
0101FF0D01|K20J-T21|Zoomer X|256
0104F20D01|K2F-T91|Scoopy i|256
0101830401|MGP-A92|CBR 1000 RR|256
01031A0501|MKN-L32|CBR 650 R ABS|256
01031A1801|MKN-U11|CBR 650 R|256
01030A0D01|K60S-T71|Click 125|384
0103070D01|K59K-T11|Click 150|384
01037C0D01|K0WF-T01|ADV 150|384
0101D00D01|K60F-T01|Click 125|384
01046D0D01|K2SF-T01|Click 160|384
01048E0D01|K0WM-TA1|ADV 160|384
01048D0D01|K0WL-T01|ADV 160|384"""
CATALOG = [dict(zip(("software_id", "family", "model", "size_kib"), line.split("|")))
           for line in CATALOG_TEXT.splitlines()]


def identify_from_log(raw_text):
    """Find an exact 5-byte software ID in a diagnostic trace, if present."""
    hex_runs = [run.upper() for run in re.findall(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{10,}(?![0-9A-Fa-f])", raw_text)]
    matches = [item for item in CATALOG if any(item["software_id"] in run for run in hex_runs)]
    return matches


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
        self.title("PTS Honda Flash Studio | วิเคราะห์ไฟล์และอุปกรณ์")
        self.geometry("960x650")
        self.configure(bg="#111216")
        self.first = None
        self.second = None
        bar = tk.Frame(self, bg="#9f1624", height=62)
        bar.pack(fill="x")
        tk.Label(bar, text="PTS  |  HONDA FLASH STUDIO", fg="white", bg="#9f1624",
                 font=("Segoe UI", 19, "bold")).pack(side="left", padx=22, pady=12)
        tk.Label(self, text="โปรไฟล์ศึกษา: " + TARGET_PART + "  •  ขนาดไฟล์อ้างอิง 256 KiB",
                 bg="#111216", fg="#eeeeee", font=("Segoe UI", 12)).pack(anchor="w", padx=20, pady=(16, 6))
        tk.Label(self, text="สถานะ ECU: ยังไม่ยืนยัน  |  อ่านแฟลช: ยังไม่มี  |  เขียนแฟลช: ยังไม่มี",
                 bg="#111216", fg="#ff7777", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20)
        controls = tk.Frame(self, bg="#111216")
        controls.pack(fill="x", padx=20, pady=18)
        for label, fn in (("เปิดไฟล์ BIN", self.open_first), ("เปรียบเทียบ BIN", self.open_second),
                          ("ตรวจรหัส ECU จาก log", self.open_log),
                          ("ค้นหาพอร์ต", self.ports), ("บันทึกรายงาน", self.save_report)):
            tk.Button(controls, text=label, command=fn, bg="#b51c2b", fg="white",
                      activebackground="#d52b3a", relief="flat", font=("Segoe UI", 11),
                      padx=13, pady=9).pack(side="left", padx=(0, 9))
        self.output = tk.Text(self, bg="#1c1e24", fg="#eeeeee", insertbackground="white",
                              font=("Consolas", 11), wrap="word", relief="flat")
        self.output.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.show("เปิดไฟล์ BIN เพื่อดูขนาด SHA-256 และข้อความระบุซอฟต์แวร์ภายในไฟล์\n"
                  "การค้นหาพอร์ตเป็นการแสดงรายการอุปกรณ์เท่านั้น ไม่ส่งข้อมูลไปยัง ECU")

    def show(self, text):
        self.output.delete("1.0", "end")
        self.output.insert("end", text)

    def open_first(self):
        path = filedialog.askopenfilename(title="เลือกไฟล์ BIN", filetypes=[("Binary", "*.bin"), ("All", "*")])
        if path:
            try:
                self.first = inspect_image(path)
                self.second = None
                self.show(json.dumps(self.first, ensure_ascii=False, indent=2))
            except OSError as exc:
                messagebox.showerror("อ่านไฟล์ไม่สำเร็จ", str(exc))

    def open_second(self):
        if not self.first:
            messagebox.showinfo("เลือกไฟล์", "เปิดไฟล์ BIN ฉบับแรกก่อน")
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
                self.show(json.dumps(report, ensure_ascii=False, indent=2))
            except OSError as exc:
                messagebox.showerror("เปรียบเทียบไม่สำเร็จ", str(exc))

    def ports(self):
        try:
            from serial.tools import list_ports
            ports = list(list_ports.comports())
            self.show("พอร์ตที่พบ (ยังไม่ได้เชื่อมต่อ ECU):\n" +
                      ("\n".join(f"{p.device} | {p.description} | VID:PID {p.vid}:{p.pid}" for p in ports)
                       if ports else "ไม่พบพอร์ต COM"))
        except ImportError:
            self.show("ต้องติดตั้ง pyserial เพื่อดูรายการพอร์ต COM")

    def open_log(self):
        path = filedialog.askopenfilename(title="เลือก log คำตอบ ECU", filetypes=[("Logs", "*.txt *.log *.jsonl"), ("All", "*")])
        if path:
            try:
                matches = identify_from_log(Path(path).read_text(encoding="utf-8"))
                self.show(json.dumps({"source": path, "matches": matches,
                    "status": "พบรหัสตรงตารางผู้ใช้" if matches else "ไม่พบรหัสตรงตาราง",
                    "note": "ต้องยืนยันว่าไบต์นี้มาจากคำตอบ ECU ไม่ใช่ TX/echo หรือข้อความใน log",
                    "flash_read": "NOT_IMPLEMENTED", "flash_write": "NOT_IMPLEMENTED"},
                    ensure_ascii=False, indent=2))
            except (OSError, UnicodeError) as exc:
                messagebox.showerror("อ่าน log ไม่สำเร็จ", str(exc))

    def save_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            try:
                Path(path).write_text(self.output.get("1.0", "end"), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("บันทึกไม่สำเร็จ", str(exc))


if __name__ == "__main__":
    Studio().mainloop()
