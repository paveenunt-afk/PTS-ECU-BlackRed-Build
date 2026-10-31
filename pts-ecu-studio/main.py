import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json, threading, datetime
import serial
from serial.tools import list_ports

DATA = Path.home() / "PTS_ECU_Studio" / "profiles.json"
FIELDS = ["name", "brand", "vehicle", "ecu_number", "mcu", "protocol", "connection", "baud", "notes"]
LABELS = ["ชื่อโปรไฟล์", "ผู้ผลิต ECU", "รุ่นรถ", "หมายเลข ECU", "MCU", "โปรโตคอล", "การเชื่อมต่อ", "Baud", "หมายเหตุ"]

class Studio:
    def __init__(self, root):
        self.root = root
        root.title("PTS ECU Studio v0.3 - Editable")
        root.geometry("1030x700")
        self.profiles = []
        self.selected = None
        self.port = None
        self.running = False
        tk.Label(root, text="PTS ECU STUDIO | ECU PROFILE MANAGER", bg="#a71919", fg="white", font=("Segoe UI", 17, "bold"), pady=12).pack(fill="x")
        body = ttk.Frame(root, padding=12)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self.listbox = tk.Listbox(left, width=30)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.select)
        for label, command in [("เพิ่มรุ่น", self.new), ("บันทึก", self.save_item), ("ลบรุ่น", self.delete), ("นำเข้า JSON", self.import_json), ("ส่งออก JSON", self.export_json)]:
            ttk.Button(left, text=label, command=command).pack(fill="x", pady=3)
        editor = ttk.LabelFrame(right, text="แก้ไขข้อมูล ECU")
        editor.pack(fill="x")
        self.vars = {}
        for i, (key, label) in enumerate(zip(FIELDS, LABELS)):
            ttk.Label(editor, text=label).grid(row=i, column=0, sticky="w", padx=7, pady=4)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(editor, textvariable=v, width=58).grid(row=i, column=1, sticky="ew", padx=7, pady=4)
        editor.columnconfigure(1, weight=1)
        conn = ttk.LabelFrame(right, text="Serial Monitor (รับข้อมูลเท่านั้น ไม่ส่งคำสั่ง ECU)")
        conn.pack(fill="both", expand=True, pady=10)
        bar = ttk.Frame(conn)
        bar.pack(fill="x", pady=5)
        self.com = tk.StringVar()
        self.baud = tk.StringVar(value="10400")
        self.ports = ttk.Combobox(bar, textvariable=self.com, width=16)
        self.ports.pack(side="left")
        ttk.Button(bar, text="ค้นหาพอร์ต", command=self.refresh).pack(side="left")
        ttk.Entry(bar, textvariable=self.baud, width=9).pack(side="left", padx=4)
        ttk.Button(bar, text="เชื่อมต่อ", command=self.connect).pack(side="left")
        ttk.Button(bar, text="ตัดการเชื่อมต่อ", command=self.disconnect).pack(side="left")
        self.status = tk.StringVar(value="ยังไม่ได้เชื่อมต่อ")
        ttk.Label(conn, textvariable=self.status).pack(anchor="w")
        self.log = tk.Text(conn, height=13, bg="#171717", fg="#dddddd")
        self.log.pack(fill="both", expand=True)
        self.load()
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def load(self):
        if DATA.exists():
            try:
                value = json.loads(DATA.read_text(encoding="utf-8"))
                self.profiles = value["profiles"] if isinstance(value, dict) else value
                if not isinstance(self.profiles, list):
                    raise ValueError("Invalid profiles")
            except Exception as e:
                messagebox.showerror("ฐานข้อมูล", str(e))
                self.profiles = []
        self.render()

    def persist(self):
        DATA.parent.mkdir(parents=True, exist_ok=True)
        tmp = DATA.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "profiles": self.profiles}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DATA)
        self.render()

    def render(self):
        self.listbox.delete(0, "end")
        for item in self.profiles:
            self.listbox.insert("end", item.get("name", "Unnamed"))

    def select(self, event=None):
        chosen = self.listbox.curselection()
        if not chosen:
            return
        self.selected = chosen[0]
        item = self.profiles[self.selected]
        for key, v in self.vars.items():
            v.set(str(item.get(key, "")))

    def new(self):
        self.selected = None
        self.listbox.selection_clear(0, "end")
        for v in self.vars.values():
            v.set("")
        self.vars["baud"].set("10400")

    def save_item(self):
        item = {key: v.get().strip() for key, v in self.vars.items()}
        if not item["name"]:
            messagebox.showwarning("ข้อมูลไม่ครบ", "กรุณาระบุชื่อโปรไฟล์")
            return
        if self.selected is None:
            self.profiles.append(item)
        else:
            self.profiles[self.selected] = item
        self.persist()

    def delete(self):
        if self.selected is not None and messagebox.askyesno("ยืนยัน", "ลบโปรไฟล์นี้?"):
            del self.profiles[self.selected]
            self.new()
            self.persist()

    def import_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
            items = value["profiles"] if isinstance(value, dict) else value
            if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
                raise ValueError("JSON ต้องมีรายการ profiles")
            self.profiles = items
            self.selected = None
            self.persist()
        except Exception as e:
            messagebox.showerror("นำเข้าไม่สำเร็จ", str(e))

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            Path(path).write_text(json.dumps({"version": 1, "profiles": self.profiles}, ensure_ascii=False, indent=2), encoding="utf-8")

    def refresh(self):
        ports = [p.device for p in list_ports.comports()]
        self.ports["values"] = ports
        if ports and not self.com.get():
            self.com.set(ports[0])

    def connect(self):
        if self.port:
            return
        try:
            self.port = serial.Serial(self.com.get(), int(self.baud.get()), timeout=0.2)
            self.running = True
            self.status.set("เชื่อมต่อ: " + self.com.get())
            threading.Thread(target=self.reader, daemon=True).start()
        except Exception as e:
            self.port = None
            messagebox.showerror("เชื่อมต่อไม่สำเร็จ", str(e))

    def reader(self):
        port = self.port
        while self.running and port and port.is_open:
            try:
                data = port.read(256)
                if data:
                    stamp = datetime.datetime.now().strftime("%H:%M:%S")
                    line = f"[{stamp}] RX: {data.hex(' ').upper()}\n"
                    self.root.after(0, lambda s=line: (self.log.insert("end", s), self.log.see("end")))
            except Exception as e:
                self.root.after(0, lambda msg=str(e): self.status.set(msg))
                break

    def disconnect(self):
        self.running = False
        port, self.port = self.port, None
        if port:
            try:
                port.close()
            except Exception:
                pass
        self.status.set("ตัดการเชื่อมต่อแล้ว")

    def close(self):
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    Studio(root)
    root.mainloop()
