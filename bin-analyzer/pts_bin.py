"""PTS BIN Tool — file inspection only, no ECU transport implemented."""
import hashlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

PAGE = 4096
MAX_SIZE = 64 * 1024 * 1024

def load_bin(path):
    with open(path, 'rb') as f:
        data = f.read(MAX_SIZE + 1)
    if not data or len(data) > MAX_SIZE:
        raise ValueError('รองรับไฟล์ขนาด 1 ไบต์ ถึง 64 MiB')
    return data

def hex_page(data, offset):
    lines = []
    for pos in range(offset, min(offset + PAGE, len(data)), 16):
        row = data[pos:pos+16]
        ascii_text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)
        lines.append(f'{pos:08X}  {row.hex(" ").upper():47}  {ascii_text}')
    return '\n'.join(lines)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PTS BIN Tool 1.0 | ตรวจไฟล์ ECU')
        self.geometry('1120x740')
        self.configure(bg='#151518')
        self.data = b''
        self.path = None
        self.offset = 0
        self.search_end = 0
        top = tk.Frame(self, bg='#222226')
        top.pack(fill='x')
        for label, action in [('เปิด .bin', self.open_file), ('บันทึกสำเนา', self.save),
                              ('ค้นหา HEX', self.search), ('ไป Offset', self.goto),
                              ('เปรียบเทียบ', self.compare), ('อ่าน / เขียน ECU', self.ecu)]:
            tk.Button(top, text=label, command=action, bg='#a91929', fg='white',
                      padx=10, pady=10).pack(side='left', padx=3, pady=8)
        self.info = tk.StringVar(value='PTS | เลือกไฟล์ .bin เพื่อเริ่มต้น')
        tk.Label(self, textvariable=self.info, bg='#151518', fg='#eeeeee',
                 justify='left', anchor='w', wraplength=1080).pack(fill='x', padx=12, pady=12)
        self.view = tk.Text(self, bg='#0d0d10', fg='#eeeeee', font=('Consolas', 11), wrap='none')
        self.view.pack(fill='both', expand=True, padx=12)
        self.view.configure(state='disabled')
        nav = tk.Frame(self, bg='#151518')
        nav.pack(fill='x', pady=10)
        tk.Button(nav, text='◀ ก่อนหน้า', command=lambda: self.move(-PAGE)).pack(side='left', padx=12)
        tk.Button(nav, text='ถัดไป ▶', command=lambda: self.move(PAGE)).pack(side='left')
        self.page = tk.StringVar()
        tk.Label(nav, textvariable=self.page, bg='#151518', fg='#eeeeee').pack(side='left', padx=15)
        tk.Label(self, text='ตรวจไฟล์เท่านั้น • ยังไม่รองรับการดูด–อัด ECU • SHA-256 ใช้เทียบไฟล์ ไม่ใช่ ECU checksum',
                 bg='#151518', fg='#f29aa3').pack(pady=5)

    def need_file(self):
        if self.data:
            return True
        messagebox.showinfo('PTS', 'กรุณาเปิดไฟล์ .bin ก่อน')
        return False

    def show(self):
        self.view.configure(state='normal')
        self.view.delete('1.0', 'end')
        self.view.insert('1.0', hex_page(self.data, self.offset))
        self.view.configure(state='disabled')
        self.page.set(f'Offset 0x{self.offset:X} | หน้า {self.offset // PAGE + 1}/{(len(self.data)+PAGE-1)//PAGE}')

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('BIN files', '*.bin'), ('All files', '*')])
        if not path:
            return
        try:
            data = load_bin(path)
            self.data, self.path, self.offset, self.search_end = data, Path(path), 0, 0
            self.info.set(f'{self.path.name} | {len(data):,} bytes\nSHA-256: {hashlib.sha256(data).hexdigest()}')
            self.show()
        except (OSError, ValueError) as exc:
            messagebox.showerror('เปิดไฟล์ไม่สำเร็จ', str(exc))

    def move(self, delta):
        if self.need_file():
            self.offset = max(0, min(self.offset + delta, ((len(self.data)-1)//PAGE)*PAGE))
            self.show()

    def save(self):
        if not self.need_file():
            return
        path = filedialog.asksaveasfilename(defaultextension='.bin', initialfile=self.path.stem+'_copy.bin')
        if not path:
            return
        try:
            target = Path(path)
            if target.resolve() == self.path.resolve() or (target.exists() and target.samefile(self.path)):
                raise ValueError('โปรดเลือกชื่อใหม่เพื่อเก็บต้นฉบับไว้')
            target.write_bytes(self.data)
            messagebox.showinfo('PTS', f'บันทึกสำเนาครบ {len(self.data):,} bytes แล้ว')
        except (OSError, ValueError) as exc:
            messagebox.showerror('บันทึกไม่สำเร็จ', str(exc))

    def goto(self):
        if not self.need_file():
            return
        text = simpledialog.askstring('Offset', 'ระบุ Offset ฐาน 16 เช่น 1000 หรือ 0x1000')
        if text is None:
            return
        try:
            pos = int(text, 16)
            if not 0 <= pos < len(self.data):
                raise ValueError()
            self.offset = pos // PAGE * PAGE
            self.show()
            self.highlight(pos, 1)
        except ValueError:
            messagebox.showerror('PTS', 'Offset ไม่ถูกต้องหรืออยู่นอกไฟล์')

    def highlight(self, pos, count):
        self.view.tag_remove('match', '1.0', 'end')
        for i in range(pos, min(pos+count, self.offset+PAGE, len(self.data))):
            row, col = divmod(i-self.offset, 16)
            self.view.tag_add('match', f'{row+1}.{10+col*3}', f'{row+1}.{12+col*3}')
        self.view.tag_config('match', background='#ad2434', foreground='white')
        self.view.see(f'{(pos-self.offset)//16+1}.0')

    def search(self):
        if not self.need_file():
            return
        text = simpledialog.askstring('ค้นหา HEX', 'ไบต์ฐาน 16 เช่น 01 02 FF (ค้นหาต่อจากครั้งก่อนและวนกลับ)')
        if text is None:
            return
        try:
            needle = bytes.fromhex(text)
            if not needle:
                raise ValueError()
        except ValueError:
            messagebox.showerror('PTS', 'กรอก HEX เป็นคู่ไบต์ให้ถูกต้อง')
            return
        pos = self.data.find(needle, self.search_end)
        if pos < 0:
            pos = self.data.find(needle)
        if pos < 0:
            messagebox.showinfo('PTS', 'ไม่พบข้อมูล')
            return
        self.search_end = pos + 1
        self.offset = pos // PAGE * PAGE
        self.show()
        self.highlight(pos, len(needle))
        messagebox.showinfo('พบข้อมูล', f'Offset 0x{pos:X} | {len(needle)} bytes')

    def compare(self):
        if not self.need_file():
            return
        path = filedialog.askopenfilename(title='เลือกไฟล์ที่จะเปรียบเทียบ')
        if not path:
            return
        try:
            other = load_bin(path)
            count = abs(len(other)-len(self.data))
            first = None
            for i, (a,b) in enumerate(zip(self.data, other)):
                if a != b:
                    count += 1
                    if first is None:
                        first = i
            if first is None and len(other) != len(self.data):
                first = min(len(other), len(self.data))
            detail = 'เหมือนกันทุกไบต์' if count == 0 else f'แตกต่าง {count:,} ตำแหน่ง (รวมส่วนที่ยาวกว่า)\nจุดแรก 0x{first:X}'
            messagebox.showinfo('ผลเปรียบเทียบ', f'ขนาด {len(self.data):,} / {len(other):,} bytes\n{detail}')
        except (OSError, ValueError) as exc:
            messagebox.showerror('PTS', str(exc))

    def ecu(self):
        messagebox.showinfo('ยังไม่มีโปรไฟล์ ECU', 'รุ่นนี้ยังไม่สื่อสารกับ ECU\nต้องระบุยี่ห้อ รุ่น ปี เบอร์ ECU และสายเชื่อมต่อก่อนพัฒนาการอ่าน–เขียนจริง\nไฟล์ .bin ไม่สามารถระบุคำสั่งแฟลชและ checksum ของกล่องได้โดยอัตโนมัติ')

if __name__ == '__main__':
    App().mainloop()
