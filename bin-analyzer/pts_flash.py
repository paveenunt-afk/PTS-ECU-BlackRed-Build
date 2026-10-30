"""PTS file catalog and experimental MEN-E21 flash UI. GPL-3.0."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pts_bin import App, load_bin
import hashlib

BASE = Path(__file__).resolve().parent
USER_ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else BASE
ROM_ROOT = USER_ROOT/'roms' if (USER_ROOT/'roms').is_dir() else BASE/'roms'


class FlashApp(App):
    def __init__(self):
        super().__init__()
        self.title('PTS BIN & Flash 2.0 | คลัง ROM + K-Line ทดลอง MEN-E21')
        self.geometry('1220x800')
        self.process = None
        self.messages = queue.Queue()
        self.busy = False
        controls = tk.Frame(self, bg='#151518')
        controls.pack(fill='x', before=self.view)
        tk.Button(controls, text='คลัง BIN ทั้งหมดที่แนบมา', command=self.catalog,
                  bg='#a91929', fg='white', padx=10, pady=8).pack(side='left', padx=12)
        tk.Label(controls, text='ดูด–อัดทดลอง: FTDI K-Line / MEN-E21 เท่านั้น | ยังไม่ผ่านการทดสอบกับกล่องจริง',
                 bg='#151518', fg='#f29aa3').pack(side='left')
        # Replace the v1 footer so it accurately states the v2 scope.
        for widget in self.winfo_children():
            if isinstance(widget, tk.Label) and 'ยังไม่รองรับ' in str(widget.cget('text')):
                widget.configure(text='ตรวจ BIN ได้ทุกไฟล์ในชุด • การเปิดไฟล์ได้ไม่ได้ยืนยันว่าแฟลชได้ • Openport ยังไม่รองรับ')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)

    def catalog(self):
        window = tk.Toplevel(self)
        window.title('คลัง ROM — ข้อมูลจากชื่อไฟล์ ไม่ใช่ผลตรวจ ECU')
        window.geometry('1080x580')
        term = tk.StringVar()
        tk.Label(window, text='ค้นหาชื่อหรือรุ่น • ดับเบิลคลิกเปิดไฟล์').pack(anchor='w', padx=12, pady=6)
        tk.Entry(window, textvariable=term).pack(fill='x', padx=12)
        frame = ttk.Frame(window)
        frame.pack(fill='both', expand=True, padx=12, pady=12)
        table = ttk.Treeview(frame, columns=('path','size'), show='headings')
        table.heading('path', text='ชื่อไฟล์ / โฟลเดอร์')
        table.heading('size', text='ขนาด (bytes)')
        table.column('path', width=850)
        table.column('size', width=110)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        files = sorted(ROM_ROOT.rglob('*.bin'))
        if not files:
            tk.Label(window, text='ยังไม่มีคลัง ROM: วางโฟลเดอร์ roms ข้าง EXE หรือใช้ปุ่มเปิด .bin').pack()
        def refresh(*_):
            table.delete(*table.get_children())
            for index, path in enumerate(files):
                label = str(path.relative_to(ROM_ROOT))
                if term.get().casefold() in label.casefold():
                    table.insert('', 'end', iid=str(index), values=(label,path.stat().st_size))
        def choose(_):
            selected = table.selection()
            if not selected:
                return
            path = files[int(selected[0])]
            try:
                data = load_bin(path)
                self.data, self.path, self.offset, self.search_end = data, path, 0, 0
                self.info.set(f'{path.name} | {len(data):,} bytes\nSHA-256: {hashlib.sha256(data).hexdigest()}')
                self.show()
            except (OSError, ValueError) as exc:
                messagebox.showerror('PTS', str(exc))
        table.bind('<Double-1>',choose)
        term.trace_add('write',refresh)
        refresh()

    def ecu(self):
        window = tk.Toplevel(self)
        window.title('ดูด–อัด ROM: รุ่นทดลอง MEN-E21')
        window.geometry('740x650')
        window.configure(bg='#151518')
        tk.Label(window, text='38770-MEN-E21 / 256 KiB / FTDI K-Line',
                 bg='#151518', fg='white', font=('Segoe UI',15,'bold')).pack(pady=12)
        details = ('ส่วนนี้ใช้ pylibftdi + libftdi/libusb และวงจรแปลง K-Line\n'
                   'ยังไม่ผ่านการทดสอบกับกล่องจริง และไม่รองรับ Openport\n'
                   'การอัดจะอ่านสำรองก่อน และยอมลบเฉพาะเมื่อ ROM จากกล่อง\n'
                   'ตรงกับ MEN-E21 อ้างอิงทุกไบต์ แล้วตรวจอ่านกลับหลังเขียน\n'
                   'หากอ่านไม่ได้ โปรแกรมจะไม่เริ่มลบ กล่องที่แก้ ROM แล้วจะถูกปฏิเสธ\n'
                   'ขณะเขียนต้องรักษาไฟเลี้ยงและสายเชื่อมต่อ')
        tk.Label(window, text=details, bg='#151518', fg='#eee', justify='left').pack(padx=15, pady=10)
        row = tk.Frame(window,bg='#151518'); row.pack(fill='x',padx=15,pady=12)
        tk.Button(row,text='ดูด ROM จากกล่อง',command=lambda:self.start_job('read')).pack(side='left',padx=5)
        tk.Button(row,text='อัด BIN ที่เปิดอยู่',command=lambda:self.start_job('write'),bg='#a91929',fg='white').pack(side='left',padx=5)
        tk.Button(row,text='เปิดคู่มือ',command=self.manual).pack(side='left',padx=5)
        output = tk.Text(window, bg='#0d0d10', fg='#eee', wrap='word')
        output.pack(fill='both',expand=True,padx=15,pady=12)
        self.job_output = output
        output.insert('end','ยังไม่ได้เชื่อมต่อ ECU\n')

    def manual(self):
        messagebox.showinfo('ติดตั้งส่วนดูด–อัด',
            'อ่าน README_TH.txt ในโฟลเดอร์โปรแกรม\nต้องมี pylibftdi และ native libftdi/libusb ที่ตรงกับสถาปัตยกรรม Python\nไม่ได้รวม DLL หรือไดรเวอร์ และไม่เปลี่ยนไดรเวอร์ให้อัตโนมัติ')

    def start_job(self, mode):
        if self.busy:
            messagebox.showinfo('PTS','กำลังทำรายการ กรุณารอจนจบ')
            return
        if mode=='write' and not self.need_file():
            return
        if mode=='write':
            from flash_engine import validate_rom
            try:
                validate_rom(self.path.read_bytes())
            except (OSError, ValueError) as exc:
                messagebox.showerror('ไฟล์ไม่ผ่าน',str(exc));return
            if not messagebox.askyesno('ยืนยันการอัด ROM รุ่นทดลอง',
                f'ไฟล์: {self.path.name}\nใช้กับ MEN-E21 ที่ยืนยันแล้วเท่านั้น\nการอัดจะลบ ROM เดิมหลังสำรอง\nต้องการเริ่มหรือไม่?'):
                return
        dest=filedialog.asksaveasfilename(title='ตั้งชื่อไฟล์สำรองจากกล่อง (ชื่อใหม่)',defaultextension='.bin')
        if not dest:return
        if Path(dest).exists() or Path(dest+'.readback.bin').exists():
            messagebox.showerror('PTS','กรุณาเลือกชื่อใหม่ที่ยังไม่มีไฟล์');return
        prefix=[sys.executable,'--flash-engine'] if getattr(sys,'frozen',False) else [sys.executable,'-u',str(BASE/'flash_engine.py')]
        args=prefix+[mode,
              str(self.path.resolve()) if mode=='write' else dest,'--part','38770-MEN-E21']
        if mode=='write':args.extend(['--backup',dest])
        self.busy=True
        def worker():
            try:
                self.process=subprocess.Popen(args,cwd=BASE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                    text=True,encoding='utf-8',errors='replace',env=self.child_env(),
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
                import os
                logdir=Path(os.environ.get('LOCALAPPDATA',str(USER_ROOT)))/'PTS_BIN_Analyzer'/'logs';logdir.mkdir(parents=True,exist_ok=True)
                from datetime import datetime
                logfile=logdir/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.txt')
                with logfile.open('w',encoding='utf-8') as log:
                    for line in self.process.stdout:
                        log.write(line);log.flush();self.messages.put(line)
                code=self.process.wait()
                self.messages.put(f'จบรายการ: exit code {code}\nบันทึก: {logfile}\n')
            except Exception as exc:
                self.messages.put(f'เปิดส่วนดูด–อัดไม่สำเร็จ: {exc}\n')
            finally:
                self.process=None;self.busy=False
        threading.Thread(target=worker,daemon=True).start()

    @staticmethod
    def child_env():
        import os
        env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
        return env

    def poll(self):
        while True:
            try:line=self.messages.get_nowait()
            except queue.Empty:break
            if hasattr(self,'job_output') and self.job_output.winfo_exists():
                self.job_output.insert('end',line);self.job_output.see('end')
        self.after(100,self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('PTS','กำลังสื่อสารกับ ECU กรุณารอให้จบก่อนปิดโปรแกรม')
            return
        self.destroy()

if __name__=='__main__':
    FlashApp().mainloop()
