"""PTS BIN Analyzer UI — GPL-3.0."""
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pts_flash import FlashApp
from bin_analysis import inspect, report_text, catalog, available_architectures, disassemble


class Analyzer(FlashApp):
    def __init__(self):
        super().__init__()
        self.title('PTS BIN Analyzer 3.0 | วิเคราะห์ ROM / อ่านคำสั่ง CPU')
        self.results=queue.Queue()
        bar=tk.Frame(self,bg='#222226');bar.pack(fill='x',before=self.view)
        for title,action in [('วิเคราะห์ BIN',self.analyze),('ตาราง ECU 83 รายการ',self.ecu_table),('ถอดคำสั่ง CPU',self.cpu)]:
            tk.Button(bar,text=title,command=action,bg='#a91929',fg='white',padx=12,pady=8).pack(side='left',padx=7,pady=7)
        tk.Label(bar,text='ออฟไลน์ • ผลวิเคราะห์ไม่เปิดสิทธิ์แฟลชกล่องเพิ่ม',bg='#222226',fg='#eee').pack(side='left',padx=10)
        self.after(100,self.poll_analysis)
        self.analyzing=False

    def analyze(self):
        if not self.need_file():return
        if self.analyzing:return
        self.analyzing=True
        source=self.path
        self.info.set(f'กำลังวิเคราะห์ {source.name} ...')
        def run():
            try:self.results.put((True,inspect(source)))
            except Exception as exc:self.results.put((False,str(exc)))
        threading.Thread(target=run,daemon=True).start()

    def poll_analysis(self):
        try:
            ok,result=self.results.get_nowait()
            self.analyzing=False
            if ok:
                self.info.set(f"วิเคราะห์เสร็จ: {Path(result['file']).name}")
                self.show_report(result)
            else:messagebox.showerror('วิเคราะห์ไม่สำเร็จ',result)
        except queue.Empty:pass
        self.after(100,self.poll_analysis)

    def show_report(self,report):
        window=tk.Toplevel(self);window.title('ผลวิเคราะห์ BIN — หลักฐานจากไฟล์');window.geometry('1100x730')
        bar=ttk.Frame(window);bar.pack(fill='x',padx=10,pady=8)
        text=report_text(report)
        def save(as_json):
            dest=filedialog.asksaveasfilename(parent=window,defaultextension='.json' if as_json else '.txt',
                filetypes=[('JSON','*.json')] if as_json else [('Text','*.txt')])
            if not dest:return
            try:
                p=Path(dest)
                if p.resolve()==Path(report['file']).resolve() or (p.exists() and p.samefile(report['file'])):
                    raise ValueError('ห้ามเขียนรายงานทับ BIN ต้นฉบับ')
                p.write_text(json.dumps(report,ensure_ascii=False,indent=2) if as_json else text,encoding='utf-8')
                messagebox.showinfo('PTS','บันทึกรายงานแล้ว')
            except (OSError,ValueError) as exc:messagebox.showerror('PTS',str(exc))
        ttk.Button(bar,text='บันทึก TXT',command=lambda:save(False)).pack(side='left',padx=5)
        ttk.Button(bar,text='บันทึก JSON',command=lambda:save(True)).pack(side='left',padx=5)
        area=tk.Text(window,bg='#101014',fg='#eee',wrap='word',font=('Consolas',11))
        scroll=ttk.Scrollbar(window,command=area.yview);area.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');area.pack(fill='both',expand=True,padx=10,pady=10)
        area.insert('1.0',text);area.configure(state='disabled')

    def ecu_table(self):
        window=tk.Toplevel(self);window.title('ข้อมูล ECU จากผู้ใช้ — ไม่ใช่รายการยืนยันการแฟลช');window.geometry('1200x600')
        tk.Label(window,text='ค่า 1/ค่า 2 เก็บตามต้นฉบับ ไม่มีการตีความเป็น address/checksum โดยอัตโนมัติ').pack(pady=8)
        query=tk.StringVar();ttk.Entry(window,textvariable=query).pack(fill='x',padx=12)
        columns=['software_id','part','model','raw_value_1','raw_value_2','size_kib','vendor']
        frame=ttk.Frame(window);frame.pack(fill='both',expand=True,padx=12,pady=12)
        table=ttk.Treeview(frame,columns=columns,show='headings')
        for key,title,width in zip(columns,['Software ID','เบอร์กล่อง','รุ่นรถ','ค่า 1','ค่า 2','ขนาด KiB','ผู้ผลิต'],[150,150,210,100,100,110,150]):
            table.heading(key,text=title);table.column(key,width=width)
        scroll=ttk.Scrollbar(frame,command=table.yview);table.configure(yscrollcommand=scroll.set)
        table.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        records=catalog()
        def refresh(*_):
            table.delete(*table.get_children());term=query.get().casefold()
            for item in records:
                if term in ' '.join(str(x) for x in item.values()).casefold():
                    table.insert('','end',values=[item[k] for k in columns])
        query.trace_add('write',refresh);refresh()

    def cpu(self):
        if not self.need_file():return
        choices=available_architectures()
        if not choices:
            messagebox.showinfo('ต้องติดตั้งส่วนถอดคำสั่ง',
                'ติดตั้ง Capstone ก่อน: python -m pip install capstone\nแล้วเปิดหน้านี้อีกครั้ง\n'
                'ต้องทราบ CPU, endianness และ file mapping จริงก่อนเลือก\n'
                'หาก CPU ไม่อยู่ในรายการ ต้องใช้ disassembler ที่รองรับ CPU นั้น')
            return
        source=self.path
        window=tk.Toplevel(self);window.title('Disassembly ตาม CPU ที่เลือก');window.geometry('1050x650')
        tk.Label(window,text='เลือก CPU ที่ยืนยันแล้วเท่านั้น • คำสั่ง CPU ไม่ใช่คำสั่ง K-Line หรือ Seed/Key').pack(pady=8)
        controls=ttk.Frame(window);controls.pack(fill='x',padx=10,pady=8)
        arch=tk.StringVar(value='');ttk.Combobox(controls,textvariable=arch,values=list(choices),state='readonly',width=28).pack(side='left')
        offset=tk.StringVar(value='0');base=tk.StringVar(value='0')
        for label,value in [('File offset (HEX)',offset),('Load base (HEX)',base)]:
            ttk.Label(controls,text=label).pack(side='left',padx=6)
            ttk.Entry(controls,textvariable=value,width=10).pack(side='left')
        output=tk.Text(window,bg='#101014',fg='#eee',font=('Consolas',11),wrap='none');output.pack(fill='both',expand=True,padx=10,pady=10)
        def decode():
            if not arch.get():messagebox.showinfo('PTS','กรุณาเลือกสถาปัตยกรรม CPU ที่ตรงกับไฟล์');return
            try:
                result=disassemble(source,arch.get(),int(offset.get(),16),int(base.get(),16))
                output.delete('1.0','end');output.insert('1.0',result)
            except Exception as exc:messagebox.showerror('ถอดคำสั่งไม่สำเร็จ',str(exc))
        ttk.Button(controls,text='อ่าน 256 bytes',command=decode).pack(side='left',padx=6)

if __name__=='__main__':Analyzer().mainloop()
