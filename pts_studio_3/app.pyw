"""PTS Studio 3.0 — independent Thai calibration-file editor."""
import base64
import csv
import io
import json
import math
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog as fd, messagebox as mb, simpledialog as sd
from pathlib import Path
from datetime import datetime
from core import Document
from engine import *
from widgets import HeatGrid,Graph,THEMES,number
from xdf_io import import_xdf
from equations import affine,calculate,parse
from patches import make_patch,apply_patch as apply_data_patch

CONFIG=Path(os.environ.get('APPDATA',str(Path.home())))/'PTS_Studio_3'/'settings.json'

class Studio(tk.Tk):
    def __init__(self):
        super().__init__();self.title('PTS STUDIO 3.1 | ห้องทำงานแมป ECU');self.geometry('1440x900');self.minsize(980,650)
        self.doc=Document();self.xdf_path=None;self.xdf_encodings={'อัตโนมัติ':'auto','Windows-874 (ไทย)':'cp874','Windows-1252':'cp1252','UTF-8':'utf-8-sig','UTF-16':'utf-16','Latin-1':'latin-1'};self.source=None;self.project=None;self.maps=[];self.versions=[];self.current=None;self.project_dirty=False;self.saved_state=b'';self.reference=None;self.popup=None;self.popgraph=None;self.sidebar_visible=True;self.full=False;self.focus_mode=False;self.settings={}
        try:self.settings=json.loads(CONFIG.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        self.theme_name=self.settings.get('theme','ดำ–แดง')
        if self.theme_name not in THEMES:self.theme_name='ดำ–แดง'
        self.theme=THEMES[self.theme_name];self.option_add('*Font',('Tahoma',10));self.build();self.apply_theme(self.theme_name);self.install_app_icon()
        self.protocol('WM_DELETE_WINDOW',self.close)
        for key,fn in [('<Control-o>',self.open_bin),('<Control-s>',self.save_project_ui),('<Control-z>',self.undo),('<Control-y>',self.redo),('<F11>',self.fullscreen),('<F10>',self.table_focus),('<Control-c>',self.copy_cells),('<Control-v>',self.paste_cells),('<Control-a>',self.select_all)]:self.bind(key,lambda e,f=fn:self.shortcut(e,f))
        self.bind('<Escape>',self.escape)
        try:self.state('zoomed')
        except tk.TclError:pass
    def shortcut(self,e,fn):
        if isinstance(e.widget,(tk.Entry,ttk.Entry,tk.Text,ttk.Combobox)) and e.keysym.lower() in ('a','c','v','z','y'):return
        self.safe(fn);return 'break'
    def safe(self,fn):
        try:return fn()
        except Exception as exc:mb.showerror('ดำเนินการไม่สำเร็จ',str(exc),parent=self)
    def button(self,parent,text,fn):
        icon=self.action_icon(text)
        b=ttk.Button(parent,text=text,image=icon,compound='left',command=lambda:self.safe(fn));b.pack(side='left',padx=3,pady=4);return b
    def build(self):
        self.menu=tk.Menu(self);self.config(menu=self.menu)
        menus=[('ไฟล์',[('เปิด BIN…',self.open_bin),('เปิดตัวอย่างฝึกใช้งาน',self.demo),('ส่งออก BIN ชื่อใหม่…',self.export_bin),('เปิดโครงการ…',self.open_project_ui),('บันทึกโครงการ…',self.save_project_ui),('ส่งออกตาราง CSV…',self.export_csv),('ส่งออกแพตช์ข้อมูล…',self.export_patch),('นำเข้าแพตช์ข้อมูล…',self.import_patch),('ปิดโปรแกรม',self.close)]),('แก้ไข',[('ย้อนกลับ  Ctrl+Z',self.undo),('ทำซ้ำ  Ctrl+Y',self.redo),('เลือกทั้งตาราง',self.select_all),('กำหนดค่า…',self.edit_selected),('บวก/ลบค่า…',lambda:self.math_edit('add')),('คูณค่า…',lambda:self.math_edit('multiply')),('ปรับเปอร์เซ็นต์…',lambda:self.math_edit('percent')),('ไล่ค่าตามแถว',lambda:self.interpolate_ui('x')),('ไล่ค่าตามคอลัมน์',lambda:self.interpolate_ui('y')),('ปรับผิวให้เรียบ',self.smooth_ui),('คัดลอกตารางที่เลือก',self.copy_cells),('วางตาราง',self.paste_cells),('คืนค่าที่เลือกจากต้นฉบับ',self.restore_selection)]),('แมป',[('นำเข้า XDF…',self.import_xdf_ui),('สร้างหรือแก้นิยามแมป…',self.map_dialog),('ตั้งค่าสูตรขั้นสูง…',self.equation_dialog),('แก้ไขนิยามแมปปัจจุบัน…',lambda:self.map_dialog(True)),('ลบแมปปัจจุบัน',self.delete_map),('นำเข้านิยาม JSON…',self.import_maps),('ส่งออกนิยาม JSON…',self.export_maps),('เรียงตามชื่อ',lambda:self.sort_maps('name')),('เรียงตามขนาด',lambda:self.sort_maps('size')),('ค้นหาบล็อกที่อาจเป็นแมป…',self.find_candidates)]),('วิเคราะห์',[('ค้นหาไบต์ HEX…',self.search_hex),('เปรียบเทียบกับ BIN…',self.compare),('ยกเลิกเปรียบเทียบ',self.clear_compare),('แก้ไขไบต์ HEX…',self.edit_hex),('ไปยังตำแหน่ง HEX…',self.goto_hex),('ส่งออกรายงานความแตกต่าง CSV…',self.diff_csv),('ข้อมูลไฟล์ / แฮช',self.file_info),('เก็บเวอร์ชันปัจจุบัน…',self.snapshot),('เรียกคืนเวอร์ชัน…',self.restore_version)]),('มุมมอง',[('ตารางเต็มพื้นที่  F10',self.table_focus),('เต็มจอ  F11',self.fullscreen),('ซ่อน/แสดงรายการแมป',self.toggle_sidebar),('กราฟ 3D หน้าต่างแยก',self.popup_3d),('ขยายช่องตาราง',lambda:self.grid.zoom(1)),('ย่อช่องตาราง',lambda:self.grid.zoom(-1))]),('ธีม',[(name,lambda n=name:self.apply_theme(n)) for name in THEMES]),('ช่วยเหลือ',[('วิธีใช้งานและขอบเขต',self.help)])]
        for label,items in menus:
            menu=tk.Menu(self.menu,tearoff=False);self.menu.add_cascade(label=label,menu=menu)
            for title,fn in items:menu.add_command(label=title,image=self.action_icon(title),compound='left',command=lambda f=fn:self.safe(f))
        self.header=ttk.Frame(self);self.header.pack(fill='x',padx=16,pady=(10,2));ttk.Label(self.header,image=self.brand_image()).pack(side='left',padx=(0,10));ttk.Label(self.header,text='PTS  /  STUDIO',font=('Tahoma',19,'bold')).pack(side='left');ttk.Label(self.header,text='   03  •  ห้องทำงานแมป ECU',style='Muted.TLabel').pack(side='left');self.file_label=tk.StringVar(value='ยังไม่ได้เปิดไฟล์');ttk.Label(self.header,textvariable=self.file_label,style='Muted.TLabel').pack(side='right')
        self.ribbon=ttk.Frame(self);self.ribbon.pack(fill='x',padx=12,pady=4)
        for text,fn in [('เปิด BIN',self.open_bin),('บันทึกโครงการ',self.save_project_ui),('ส่งออก BIN',self.export_bin),('เปิด XDF',self.import_xdf_ui),('สร้างแมป',self.map_dialog),('ย้อนกลับ',self.undo),('ทำซ้ำ',self.redo),('กราฟ 3D ↗',self.popup_3d),('ตารางเต็มพื้นที่',self.table_focus),('เต็มจอ F11',self.fullscreen)]:self.button(self.ribbon,text,fn)
        self.body=ttk.Panedwindow(self,orient='horizontal');self.body.pack(fill='both',expand=True,padx=12,pady=5)
        self.side=ttk.Frame(self.body,width=250);self.body.add(self.side,weight=1);ttk.Label(self.side,text='คลังแมป',font=('Tahoma',13,'bold')).pack(anchor='w',padx=10,pady=10)
        self.query=tk.StringVar();ttk.Entry(self.side,textvariable=self.query).pack(fill='x',padx=8);self.query.trace_add('write',lambda *a:self.refresh_maps())
        self.maplist=tk.Listbox(self.side,exportselection=False,borderwidth=0,highlightthickness=0,activestyle='none',font=('Tahoma',11),width=27);self.maplist.pack(fill='both',expand=True,padx=8,pady=10);self.maplist.bind('<<ListboxSelect>>',self.choose_map)
        ttk.Label(self.side,text='มุมสีทอง = ค่าต่างจากไฟล์อ้างอิง\nลากเลือกช่อง • Shift+คลิกเลือกช่วง\nดับเบิลคลิก / Enter เพื่อแก้ค่า',style='Muted.TLabel',justify='left').pack(anchor='w',padx=10,pady=10)
        self.work=ttk.Frame(self.body);self.body.add(self.work,weight=6)
        self.map_title=tk.StringVar(value='พื้นที่ตาราง');ttk.Label(self.work,textvariable=self.map_title,font=('Tahoma',14,'bold')).pack(anchor='w',padx=6,pady=(5,2))
        self.map_details=tk.StringVar(value='เปิด BIN หรือเมนู ไฟล์ → เปิดตัวอย่างฝึกใช้งาน');ttk.Label(self.work,textvariable=self.map_details,style='Muted.TLabel').pack(anchor='w',padx=6,pady=(0,5))
        xdfbar=ttk.Frame(self.work);xdfbar.pack(fill='x',padx=6,pady=3);self.xdf_label=tk.StringVar(value='XDF: ยังไม่ได้เลือก');ttk.Label(xdfbar,textvariable=self.xdf_label,style='Muted.TLabel').pack(side='left');ttk.Label(xdfbar,text='รหัสอักขระ XDF:').pack(side='right');self.xdf_encoding_var=tk.StringVar(value='อัตโนมัติ');enc=ttk.Combobox(xdfbar,textvariable=self.xdf_encoding_var,values=tuple(self.xdf_encodings),state='readonly',width=20);enc.pack(side='right',padx=8);enc.bind('<<ComboboxSelected>>',lambda e:self.safe(lambda:self.load_xdf(self.xdf_path) if self.xdf_path and self.doc.data else None))
        self.editbar=ttk.Frame(self.work);self.editbar.pack(fill='x')
        for text,fn in [('กำหนดค่า',self.edit_selected),('บวก/ลบ',lambda:self.math_edit('add')),('เปอร์เซ็นต์',lambda:self.math_edit('percent')),('ไล่ค่า →',lambda:self.interpolate_ui('x')),('ไล่ค่า ↓',lambda:self.interpolate_ui('y')),('ปรับผิว',self.smooth_ui),('คัดลอก',self.copy_cells),('วาง',self.paste_cells)]:self.button(self.editbar,text,fn)
        self.tabs=ttk.Notebook(self.work);self.tabs.pack(fill='both',expand=True,pady=5)
        self.grid=HeatGrid(self.tabs,self.selection_changed,self.edit_selected,self.theme);self.tabs.add(self.grid,text='  ตารางสี  ')
        self.g2=Graph(self.tabs,self.theme,'2d');self.tabs.add(self.g2,text='  กราฟ 2D  ');self.g3=Graph(self.tabs,self.theme,'3d');self.tabs.add(self.g3,text='  กราฟ 3D  ')
        self.hex=tk.Text(self.tabs,wrap='none',font=('Consolas',11),state='disabled',borderwidth=0);self.tabs.add(self.hex,text='  ไบต์ฐานสิบหก  ')
        self.foot=ttk.Frame(self);self.foot.pack(fill='x',padx=16,pady=(3,10));self.status=tk.StringVar(value='พร้อมใช้งาน • โปรแกรมแก้ไขไฟล์ ไม่มีการเชื่อมต่อ ECU');ttk.Label(self.foot,textvariable=self.status,style='Muted.TLabel').pack(side='left');self.stats=tk.StringVar();ttk.Label(self.foot,textvariable=self.stats).pack(side='right')
    def asset(self,name):
        return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/name
    def brand_image(self):
        if not hasattr(self,'_brand'):
            self._brand=tk.PhotoImage(file=str(self.asset('pts.png'))).subsample(4,4)
        return self._brand
    def action_icon(self,text):
        if not hasattr(self,'_icons'):self._icons={}
        entries=[('เปิด BIN','open'),('เปิด XDF','open'),('บันทึก','save'),('ส่งออก','export'),('สร้างแมป','table'),('ย้อนกลับ','undo'),('ทำซ้ำ','redo'),('กราฟ','graph'),('เต็มจอ','fullscreen'),('เต็มพื้นที่','fullscreen'),('คัดลอก','copy'),('วาง','paste'),('เปอร์เซ็นต์','percent'),('บวก','add'),('กำหนดค่า','edit'),('ปรับผิว','smooth'),('→','right'),('↓','down')]
        name=next((name for word,name in entries if word in text),'table')
        if name not in self._icons:self._icons[name]=tk.PhotoImage(file=str(self.asset(name+'.png')))
        return self._icons[name]
    def install_app_icon(self,win=None):
        win=win or self
        if not hasattr(self,'_window_icon'):self._window_icon=tk.PhotoImage(file=str(self.asset('pts.png')))
        win.iconphoto(True,self._window_icon)
        if sys.platform=='win32':
            try:win.iconbitmap(str(self.asset('pts.ico')))
            except tk.TclError:pass
    def apply_theme(self,name):
        self.theme_name=name;self.theme=THEMES[name];t=self.theme;self.config(bg=t['bg']);s=ttk.Style(self);s.theme_use('clam');s.configure('.',font=('Tahoma',10),background=t['panel'],foreground=t['fg'],fieldbackground=t['bg']);s.configure('TFrame',background=t['panel']);s.configure('Muted.TLabel',foreground=t['muted']);s.configure('TButton',padding=(10,7),background=t['panel'],borderwidth=0);s.map('TButton',background=[('active',t['accent'])]);s.configure('TNotebook',background=t['panel'],borderwidth=0);s.configure('TNotebook.Tab',padding=(14,8));s.map('TNotebook.Tab',background=[('selected',t['accent'])],foreground=[('selected','#ffffff')]);self.maplist.config(bg=t['bg'],fg=t['fg'],selectbackground=t['accent'],selectforeground='#ffffff');self.hex.config(bg=t['bg'],fg=t['fg'],insertbackground=t['fg'])
        self.grid.theme=t;self.grid.queue()
        for g in (self.g2,self.g3,self.popgraph):
            if g and g.winfo_exists():g.theme=t;g.draw()
        self.settings['theme']=name;CONFIG.parent.mkdir(parents=True,exist_ok=True);CONFIG.write_text(json.dumps(self.settings),encoding='utf-8')
    def is_dirty(self):return self.project_dirty or bytes(self.doc.data)!=self.saved_state
    def confirm_discard(self):return not self.is_dirty() or mb.askyesno('ข้อมูลยังไม่บันทึก','เปิดงานใหม่หรือปิดโปรแกรมโดยไม่บันทึกการเปลี่ยนแปลงหรือไม่?',parent=self)
    def close(self):
        if self.confirm_discard():self.destroy()
    def open_bin(self):
        if not self.confirm_discard():return
        path=fd.askopenfilename(title='เปิดไฟล์ BIN',filetypes=[('ไฟล์ BIN','*.bin'),('ทุกไฟล์','*.*')])
        if not path:return
        doc=Document(checked_bytes(path));self.new_document(doc,Path(path))
        if self.xdf_path:self.load_xdf(self.xdf_path)
    def new_document(self,doc,path,maps=None,versions=None):
        self.doc=doc;self.source=path;self.project=None;self.reference=None;self.versions=versions or [];self.project_dirty=False;self.saved_state=bytes(doc.data);self.maps=maps or [];self.current=None;self.grid.selected=set()
        if self.maps:self.current=self.maps[0]
        self.refresh_maps();self.render()
    def demo(self):
        if not self.confirm_discard():return
        self.xdf_path=None
        raw=bytearray(16384)
        for r in range(16):
            for c in range(16):
                v=round(900+180*r+65*c+300*math.sin(c/3)*math.cos(r/4));a=1024+2*(r*16+c);raw[a:a+2]=v.to_bytes(2,'little')
        doc=Document(raw);m=spec(dict(name='ตัวอย่างสังเคราะห์ — ฝึกแก้ไขเท่านั้น',address=1024,rows=16,cols=16,bits=16,factor=.01,unit='หน่วยตัวอย่าง',x_axis=[500+500*i for i in range(16)],y_axis=[10*i for i in range(16)]),doc);self.new_document(doc,None,[m]);self.status.set('ข้อมูลสังเคราะห์สำหรับฝึกใช้งาน ไม่ใช่ไฟล์รถจริง')
    def refresh_maps(self):
        self.maplist.delete(0,'end');self.visible=[m for m in self.maps if self.query.get().lower() in (m['name']+' '+m.get('category','')).lower()]
        for m in self.visible:self.maplist.insert('end',f"{m['name']}\n".strip()+f"  ·  {m['rows']}×{m['cols']}")
    def choose_map(self,e):
        if self.maplist.curselection():self.current=self.visible[self.maplist.curselection()[0]];self.grid.selected=set();self.grid.anchor=None;self.safe(self.render)
    def render(self):
        if not self.current:
            self.map_title.set('รออ่านแมปจาก XDF');self.map_details.set('เปิด BIN แล้วเลือก XDF ที่ตรงกับไฟล์ เพื่อแสดงตารางตามนิยาม');self.xdf_label.set('XDF: '+(Path(self.xdf_path).name if self.xdf_path else 'ยังไม่ได้เลือก'));self.grid.set_data([],None)
            for graph in (self.g2,self.g3,self.popgraph):
                if graph and graph.winfo_exists():graph.set_data([],None)
            self.hex.config(state='normal');self.hex.delete('1.0','end');self.hex.config(state='disabled');self.file_label.set((self.source.name if self.source else 'ยังไม่ได้เลือก BIN')+f'   {len(self.doc.data):,} ไบต์');self.status.set('ยังไม่แสดงตารางจนกว่าจะอ่านนิยามแมปจาก XDF');return
        self.xdf_label.set('XDF: '+(Path(self.xdf_path).name if self.xdf_path else 'นิยามตัวอย่าง / โครงการ'))
        m=self.current;vals=display_values(self.doc,m);raw=raw_values(self.doc,m);reference=Document(self.reference if self.reference is not None else self.doc.original);changed=set()
        try:other=raw_values(reference,m);changed={i for i,(a,b) in enumerate(zip(raw,other)) if a!=b}
        except ValueError:pass
        formula=m.get('equation') or f"X × {m['factor']:g} + {m['offset']:g}"
        self.map_title.set(m['name']+('  [อ่านอย่างเดียว]' if m.get('read_only') else ''));self.map_details.set(f"0x{m['address']:08X}   •   {m['rows']} × {m['cols']}   •   {m['bits']} บิต   •   {'ไบต์ต่ำก่อน' if m['endian']=='little' else 'ไบต์สูงก่อน'}   •   ค่าแสดง = {formula}   {m['unit']}")
        self.file_label.set((self.source.name if self.source else 'ตัวอย่าง / โครงการ')+f'   {len(self.doc.data):,} ไบต์'+('   ● เปลี่ยนแปลง' if self.is_dirty() else ''))
        self.grid.set_data(vals,m,changed)
        for graph in (self.g2,self.g3,self.popgraph):
            if graph and graph.winfo_exists():graph.set_data(vals,m)
        a=m['address'];blob=self.doc.data[a:min(a+8192,len(self.doc.data))];lines=[]
        for i in range(0,len(blob),16):
            chunk=blob[i:i+16];lines.append(f'{a+i:08X}   '+ ' '.join(f'{x:02X}' for x in chunk).ljust(47)+'   '+''.join(chr(x) if 32<=x<127 else '.' for x in chunk))
        self.hex.config(state='normal');self.hex.delete('1.0','end');self.hex.insert('end','\n'.join(lines));self.hex.config(state='disabled');self.status.set(f'ช่องที่ต่างจาก'+('ไฟล์เปรียบเทียบ' if self.reference is not None else 'ต้นฉบับ')+f': {len(changed):,}  •  Ctrl+ล้อเมาส์: ซูมตาราง  •  F10: ตารางเต็มพื้นที่')
    def selection_changed(self):
        if not self.current or not self.grid.values:self.stats.set('');return
        vals=[self.grid.values[i] for i in self.grid.selected];self.stats.set(f'เลือก {len(vals)} ช่อง'+(f'   ต่ำสุด {number(min(vals))}   สูงสุด {number(max(vals))}' if vals else ''))
    def require_selection(self):
        if not self.current or not self.grid.selected:raise ValueError('เปิดไฟล์และเลือกช่องในตารางก่อน')
        return sorted(self.grid.selected)
    def apply_updates(self,updates):
        change_cells(self.doc,self.current,updates);self.project_dirty=True;self.render()
    def edit_selected(self):
        indices=self.require_selection();value=sd.askfloat('กำหนดค่า',f'ค่าใหม่สำหรับ {len(indices)} ช่อง ({self.current["unit"] or "ค่าตามสูตรที่กำหนด"}):',initialvalue=self.grid.values[indices[0]],parent=self)
        if value is not None:self.apply_updates({i:value for i in indices})
    def math_edit(self,mode):
        indices=self.require_selection();title={'add':'บวก/ลบค่า เช่น 2 หรือ -2','multiply':'คูณค่าด้วยจำนวน เช่น 1.02','percent':'เพิ่ม/ลดเปอร์เซ็นต์ เช่น 2 หรือ -2'}[mode];value=sd.askfloat('แก้ไขช่องที่เลือก',title,parent=self)
        if value is None:return
        vals=display_values(self.doc,self.current);updates={i:vals[i]+value if mode=='add' else vals[i]*value if mode=='multiply' else vals[i]*(1+value/100) for i in indices};self.apply_updates(updates)
    def interpolate_ui(self,axis):
        indices=self.require_selection();m=self.current;self.apply_updates(interpolate(display_values(self.doc,m),m['rows'],m['cols'],indices,axis))
    def smooth_ui(self):
        indices=self.require_selection();m=self.current;self.apply_updates(smooth(display_values(self.doc,m),m['rows'],m['cols'],indices))
    def select_all(self):self.grid.all()
    def undo(self):
        if self.doc.undo_stack:self.doc.undo();self.project_dirty=True;self.render()
    def redo(self):
        if self.doc.redo_stack:self.doc.redo();self.project_dirty=True;self.render()
    def restore_selection(self):
        indices=self.require_selection();restore_raw_cells(self.doc,self.current,indices);self.project_dirty=True;self.render()
    def copy_cells(self):
        indices=self.require_selection();cols=self.current['cols'];rs=[i//cols for i in indices];cs=[i%cols for i in indices];values=display_values(self.doc,self.current);text='\n'.join('\t'.join(format(values[r*cols+c],'.12g') if r*cols+c in self.grid.selected else '' for c in range(min(cs),max(cs)+1)) for r in range(min(rs),max(rs)+1));self.clipboard_clear();self.clipboard_append(text);self.status.set('คัดลอกค่าตารางที่เลือกแล้ว')
    def paste_cells(self):
        indices=self.require_selection();text=self.clipboard_get().strip();lines=text.splitlines()
        if not lines or len(text)>1024*1024:raise ValueError('ข้อมูลคลิปบอร์ดว่างหรือใหญ่เกินกำหนด')
        delimiter='\t' if '\t' in text else ',';matrix=list(csv.reader(lines,delimiter=delimiter));m=self.current;sr,sc=divmod(indices[0],m['cols']);updates={}
        for dr,row in enumerate(matrix):
            for dc,cell in enumerate(row):
                if not cell.strip():continue
                if sr+dr>=m['rows'] or sc+dc>=m['cols']:raise ValueError('ข้อมูลวางเกินขอบเขตตาราง จึงยังไม่เปลี่ยนข้อมูล')
                updates[(sr+dr)*m['cols']+sc+dc]=float(cell)
        self.apply_updates(updates)
    def map_dialog(self,editing=False):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อนสร้างแมป')
        base=dict(self.current) if self.current else dict(name='แมปใหม่',address=0,rows=16,cols=16,bits=16,endian='little',signed=False,factor=1,offset=0,unit='')
        if not editing:base['name']='แมปใหม่';base.pop('xdf_id',None)
        win=tk.Toplevel(self);win.title('นิยามแมป / การแปลงค่า');win.transient(self);win.grab_set();frame=ttk.Frame(win,padding=20);frame.pack(fill='both',expand=True);fields={}
        options={'endian':{'little':'ไบต์ต่ำก่อน','big':'ไบต์สูงก่อน'},'data_type':{'integer':'จำนวนเต็ม','float':'ทศนิยม 32 บิต'},'layout':{'row':'เรียงตามแถว','column':'เรียงตามคอลัมน์'}}
        labels=[('name','ชื่อแมป'),('address','ตำแหน่ง HEX'),('rows','จำนวนแถว (1–128)'),('cols','จำนวนคอลัมน์ (1–128)'),('bits','ขนาดข้อมูล (8 / 16 / 32)'),('endian','ลำดับไบต์'),('factor','ตัวคูณ'),('offset','ค่าชดเชย'),('unit','หน่วย'),('data_type','ชนิดข้อมูล'),('layout','การจัดเก็บ'),('x_axis','แกนคอลัมน์ คั่นด้วย ,'),('y_axis','แกนแถว คั่นด้วย ,')]
        for row,(key,label) in enumerate(labels):
            ttk.Label(frame,text=label).grid(row=row,column=0,sticky='w',padx=5,pady=4);default=base.get(key,'integer' if key=='data_type' else 'row' if key=='layout' else '')
            if key=='address':default=f'{base["address"]:X}'
            if key in ('x_axis','y_axis'):default=', '.join(number(v) for v in default) if isinstance(default,list) else ''
            v=tk.StringVar(value=options[key].get(default,default) if key in options else str(default));fields[key]=v
            if key in ('bits','endian','data_type','layout'):entry=ttk.Combobox(frame,textvariable=v,values=('8','16','32') if key=='bits' else tuple(options[key].values()),state='readonly',width=45)
            else:entry=ttk.Entry(frame,textvariable=v,width=48)
            entry.grid(row=row,column=1,sticky='ew',padx=5,pady=4)
        signed=tk.BooleanVar(value=base['signed']);ttk.Checkbutton(frame,text='ค่าดิบมีเครื่องหมายบวก/ลบ',variable=signed).grid(row=13,column=1,sticky='w');ttk.Label(frame,text='แกนว่าง = ใช้หมายเลขช่อง • แกนที่ระบุเป็นค่าคงที่\nค่าจำนวนเต็มปัดเมื่อบันทึก • ถ้ามีสูตรขั้นสูง สูตรนั้นจะใช้แทนตัวคูณ/ค่าชดเชย',style='Muted.TLabel').grid(row=14,column=0,columnspan=2,sticky='w',pady=10)
        def commit():
            data=dict(base);data.update({k:v.get() for k,v in fields.items()});
            for k,opts in options.items():data[k]=next(code for code,label in opts.items() if label==data[k])
            data['address']=int(data['address'],16);data['signed']=signed.get()
            for k in ('x_axis','y_axis'):
                if not data[k].strip():del data[k]
                else:data[k]=[float(s.strip()) for s in data[k].split(',')]
            new=spec(data,self.doc);display_values(self.doc,new)
            if editing and self.current in self.maps:self.maps[self.maps.index(self.current)]=new
            else:self.maps.append(new)
            self.current=new;self.project_dirty=True;self.grid.selected=set();self.grid.anchor=None;self.refresh_maps();self.render();win.destroy()
        ttk.Button(frame,text='ใช้และบันทึกนิยาม',command=lambda:self.safe(commit)).grid(row=15,column=1,sticky='e',pady=8);win.bind('<Escape>',lambda e:win.destroy())
    def delete_map(self):
        if self.current in self.maps and mb.askyesno('ลบนิยาม','ลบเฉพาะนิยามแมปปัจจุบัน? ข้อมูล BIN จะยังอยู่',parent=self):self.maps.remove(self.current);self.project_dirty=True;self.refresh_maps()
    def sort_maps(self,key):self.maps.sort(key=(lambda m:m['name'].lower()) if key=='name' else (lambda m:m['rows']*m['cols']*m['bits']));self.project_dirty=True;self.refresh_maps()
    def import_maps(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        path=fd.askopenfilename(title='นำเข้านิยาม PTS JSON',filetypes=[('JSON','*.json')])
        if path:
            if Path(path).stat().st_size>4*1024*1024:raise ValueError('ไฟล์นิยามใหญ่เกิน 4 MB')
            maps=[spec(m,self.doc) for m in json.loads(Path(path).read_text(encoding='utf-8'))];self.maps.extend(maps);self.project_dirty=True;self.refresh_maps()
    def export_maps(self):
        path=fd.asksaveasfilename(title='ส่งออกนิยามแมป',defaultextension='.json')
        if path:Path(path).write_text(json.dumps(self.maps,ensure_ascii=False,indent=2),encoding='utf-8')
    def export_csv(self):
        if not self.current:raise ValueError('เลือกแมปก่อน')
        path=fd.asksaveasfilename(title='ส่งออกตารางพร้อมแกน',defaultextension='.csv')
        if path:
            m=self.current;vals=display_values(self.doc,m)
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f);writer.writerow(['แกนแถว / แกนคอลัมน์']+m['x_axis'])
                for r in range(m['rows']):writer.writerow([m['y_axis'][r]]+vals[r*m['cols']:(r+1)*m['cols']])
    def export_bin(self):
        if not self.doc.data:raise ValueError('ยังไม่ได้เปิดไฟล์')
        path=fd.asksaveasfilename(title='ส่งออก BIN ชื่อใหม่',initialfile=(self.source.stem if self.source else 'PTS')+'_modified.bin',defaultextension='.bin')
        if not path:return
        if self.source and Path(path).resolve()==self.source.resolve():raise ValueError('ใช้ชื่อใหม่เพื่อรักษาไฟล์ต้นฉบับ')
        Path(path).write_bytes(self.doc.data);self.status.set('ส่งออก BIN แล้ว • ยังไม่ได้ตรวจหรือแก้ checksum เฉพาะ ECU')
    def save_project_ui(self):
        if not self.doc.data:raise ValueError('ยังไม่ได้เปิดไฟล์')
        path=fd.asksaveasfilename(title='บันทึกโครงการ PTS',defaultextension='.pts3',initialfile=self.project.stem+'.pts3' if self.project else 'PTS_Project.pts3')
        if not path:return
        
        if self.source and Path(path).resolve()==self.source.resolve():raise ValueError('เลือกชื่อโครงการใหม่เพื่อรักษาไฟล์ BIN ต้นฉบับ')
        save_project(path,self.doc,self.maps,self.versions);self.project=Path(path);self.project_dirty=False
        # Preserve original BIN independently while recording the saved working state.
        self.saved_state=bytes(self.doc.data);self.render();self.status.set('บันทึกโครงการ พร้อมต้นฉบับและเวอร์ชันแล้ว')
    def open_project_ui(self):
        if not self.confirm_discard():return
        path=fd.askopenfilename(title='เปิดโครงการ PTS 3',filetypes=[('โครงการ PTS','*.pts3 *.pts2')])
        if path:
            doc,maps,versions=load_project(path);self.xdf_path=None;self.new_document(doc,None,maps,versions);self.project=Path(path);self.saved_state=bytes(doc.data);self.render()
    def snapshot(self):
        if not self.doc.data:raise ValueError('เปิดไฟล์ก่อน')
        if len(self.versions)>=5:raise ValueError('เก็บได้ 5 เวอร์ชันต่อโครงการในรุ่นนี้')
        name=sd.askstring('เก็บเวอร์ชัน','ชื่อเวอร์ชัน:',initialvalue=datetime.now().strftime('%Y-%m-%d %H:%M'),parent=self)
        if name:self.versions.append(dict(name=name,data=base64.b64encode(self.doc.data).decode()));self.project_dirty=True;self.status.set('เก็บเวอร์ชันแล้ว อย่าลืมบันทึกโครงการ')
    def restore_version(self):
        if not self.versions:raise ValueError('ยังไม่มีเวอร์ชันที่เก็บไว้')
        num=sd.askinteger('เลือกเวอร์ชัน','\n'.join(f'{i+1}. {v["name"]}' for i,v in enumerate(self.versions)),minvalue=1,maxvalue=len(self.versions),parent=self)
        if num:
            data=base64.b64decode(self.versions[num-1]['data']);self.doc.edit_bytes(0,data);self.project_dirty=True;self.render()
    def search_hex(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        text=sd.askstring('ค้นหาไบต์','ใส่ไบต์ HEX เช่น 01 FF A0:',parent=self)
        if text is None:return
        pattern=bytes.fromhex(text)
        if not pattern:raise ValueError('ระบุไบต์ก่อนค้นหา')
        address=self.doc.data.find(pattern)
        if address<0:mb.showinfo('ผลการค้นหา','ไม่พบข้อมูล',parent=self);return
        cols=min(16,len(self.doc.data)-address);rows=min(16,(len(self.doc.data)-address)//cols);self.current=spec(dict(name='ผลค้นหา HEX',address=address,rows=rows,cols=cols,bits=8),self.doc);self.render();self.tabs.select(3)
    def compare(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        path=fd.askopenfilename(title='เลือก BIN อ้างอิง')
        if not path:return
        data=checked_bytes(path)
        if len(data)!=len(self.doc.data):raise ValueError('การเปรียบเทียบสีในรุ่นนี้ต้องใช้ไฟล์ขนาดเท่ากัน')
        total=sum(a!=b for a,b in zip(self.doc.data,data));self.reference=data;self.render();mb.showinfo('ผลเปรียบเทียบ',f'ต่างกัน {total:,} ไบต์\nมุมสีทองในตารางแสดงช่องที่ต่างจากไฟล์อ้างอิง',parent=self)
    def clear_compare(self):self.reference=None;self.render()
    def file_info(self):mb.showinfo('ข้อมูลไฟล์',f'ขนาด {len(self.doc.data):,} ไบต์\n{self.doc.hashes()}\n\nSHA-256 / CRC32 เป็นแฮชทั่วไป ไม่ใช่การแก้ checksum ECU',parent=self)
    def find_candidates(self):
        if not self.current:raise ValueError('เปิด BIN ก่อน')
        if not mb.askokcancel('ค้นหาบล็อกที่อาจเป็นแมป','ตรวจบล็อก 16×16 ที่มีค่าต่อเนื่องใน 2 MB แรก\nใช้บิตและลำดับไบต์ของแมปปัจจุบัน ผลลัพธ์เป็นเพียงจุดเริ่มตรวจ ไม่ใช่การยืนยันชนิดแมป',parent=self):return
        found=candidate_regions(self.doc,self.current['bits'],self.current['endian']);win=tk.Toplevel(self);win.title('บล็อกที่อาจเป็นแมป — ต้องตรวจเอง');lst=tk.Listbox(win,width=60,height=20);lst.pack(fill='both',expand=True,padx=10,pady=10)
        for score,a in found:lst.insert('end',f'0x{a:08X}   ความต่อเนื่อง {score*100:.1f}%')
        if not found:lst.insert('end','ไม่พบบล็อกตามเกณฑ์')
        def use():
            if not found or not lst.curselection():return
            score,a=found[lst.curselection()[0]];m=spec(dict(name=f'บล็อกรอตรวจ 0x{a:X}',address=a,rows=16,cols=16,bits=self.current['bits'],endian=self.current['endian']),self.doc);self.current=m;self.render();win.destroy()
        ttk.Button(win,text='เปิดบล็อกที่เลือก',command=lambda:self.safe(use)).pack(pady=8)
    def toggle_sidebar(self):
        if self.sidebar_visible:self.body.forget(self.side)
        else:self.body.insert(0,self.side,weight=1)
        self.sidebar_visible=not self.sidebar_visible
    def fullscreen(self):self.full=not self.full;self.attributes('-fullscreen',self.full)
    def table_focus(self):
        self.tabs.select(0)
        if not self.focus_mode:
            self.focus_side=self.sidebar_visible
            if self.sidebar_visible:self.toggle_sidebar()
            self.header.pack_forget();self.ribbon.pack_forget();self.focus_mode=True
        else:
            self.header.pack(before=self.body,fill='x',padx=16,pady=(10,2));self.ribbon.pack(before=self.body,fill='x',padx=12,pady=4)
            if self.focus_side and not self.sidebar_visible:self.toggle_sidebar()
            self.focus_mode=False
    def escape(self,e=None):
        if self.full:self.full=False;self.attributes('-fullscreen',False)
        elif self.focus_mode:self.table_focus()
    def popup_3d(self):
        if self.popup and self.popup.winfo_exists():self.popup.lift();return
        self.popup=tk.Toplevel(self);self.popup.title('PTS | กราฟพื้นผิว 3D');self.install_app_icon(self.popup);self.popup.geometry('1000x720');self.popgraph=Graph(self.popup,self.theme,'3d');self.popgraph.pack(fill='both',expand=True);self.popup.bind('<Escape>',lambda e:self.popup.destroy())
        if self.current:self.popgraph.set_data(display_values(self.doc,self.current),self.current)
    def import_xdf_ui(self):
        path=fd.askopenfilename(title='เลือก XDF เพื่ออ่านรายการแมป',filetypes=[('XDF','*.xdf'),('ทุกไฟล์','*.*')])
        if not path:return
        if not self.doc.data:
            self.status.set('เลือกไฟล์ BIN ที่ตรงกับ XDF นี้');self.open_bin()
        if not self.doc.data:return
        self.load_xdf(path)
    def load_xdf(self,path,show_report=True):
        encoding=self.xdf_encodings[self.xdf_encoding_var.get()];maps,report=import_xdf(path,self.doc,encoding)
        self.xdf_path=str(path);self.maps=maps;self.current=maps[0] if maps else None;self.query.set('');self.grid.selected=set();self.grid.anchor=None;self.project_dirty=True;self.refresh_maps();self.render()
        if maps:self.maplist.selection_set(0);self.maplist.activate(0);self.tabs.select(0)
        if show_report:self.text_window('รายงานอ่าน XDF',f'อ่านได้ {len(maps)} รายการจาก {Path(path).name}\nตำแหน่ง ขนาด แกน และสูตรอ่านจาก XDF ไม่แก้ไบต์ BIN ระหว่างอ่าน\n\n'+'\n\n'.join(report))
        return report
    def equation_dialog(self):
        if not self.current:raise ValueError('เลือกแมปก่อน')
        m=self.current;win=tk.Toplevel(self);win.title('สูตรแสดงค่า / สูตรแปลงกลับ');win.transient(self);win.grab_set();frame=ttk.Frame(win,padding=20);frame.pack(fill='both',expand=True)
        eq=tk.StringVar(value=m.get('equation') or f"X*{m['factor']}+({m['offset']})");inv=tk.StringVar(value=m.get('inverse',''))
        ttk.Label(frame,text='สูตรแสดงค่า (X = ค่าดิบ)').pack(anchor='w');ttk.Entry(frame,textvariable=eq,width=65).pack(fill='x',pady=6);ttk.Label(frame,text='สูตรแปลงกลับ (X = ค่าแสดง) เว้นว่างได้สำหรับสูตรเชิงเส้น').pack(anchor='w');ttk.Entry(frame,textvariable=inv,width=65).pack(fill='x',pady=6)
        ttk.Label(frame,text='รองรับตัวเลข X และ + - * / ** เท่านั้น ไม่มีการรันโค้ด Python\nตัวอย่าง: X/100  →  สูตรกลับ X*100\nสูตรไม่เป็นเชิงเส้นและไม่ระบุสูตรกลับ = อ่านอย่างเดียว\nสูตรที่กำหนดในหน้านี้มีผลแทนตัวคูณและค่าชดเชยเดิม',style='Muted.TLabel').pack(anchor='w',pady=10)
        def commit():
            new=dict(m);new['equation']=eq.get();new['inverse']=inv.get();parse(new['equation']);new.pop('read_only',None);new.pop('read_only_reason',None)
            if new['inverse']:parse(new['inverse'])
            else:
                try:
                    a,b=affine(new['equation'])
                    if not a:raise ValueError('สูตรคงที่')
                except ValueError:new['read_only']=True;new['read_only_reason']='สูตรนี้ยังไม่มีสูตรแปลงกลับ'
            new=spec(new,self.doc);vals=display_values(self.doc,new)
            if not new.get('read_only'):
                for value in vals:raw_from_display(value,new)
            if m in self.maps:self.maps[self.maps.index(m)]=new
            else:self.maps.append(new)
            self.current=new;self.project_dirty=True;self.refresh_maps();self.render();win.destroy()
        ttk.Button(frame,text='ตรวจสูตรและใช้กับแมป',command=lambda:self.safe(commit)).pack(anchor='e');win.bind('<Escape>',lambda e:win.destroy())
    def edit_hex(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        addr=sd.askstring('แก้ไบต์ HEX','ตำแหน่งฐานสิบหก:',initialvalue=f"{self.current['address']:X}" if self.current else '0',parent=self)
        if addr is None:return
        a=int(addr,16)
        if not 0<=a<len(self.doc.data):raise ValueError('ตำแหน่งอยู่นอกไฟล์')
        initial=' '.join(f'{v:02X}' for v in self.doc.data[a:a+16]);text=sd.askstring('แก้ไบต์ HEX','ไบต์ใหม่ (ไม่เกิน 256 ไบต์):',initialvalue=initial,parent=self)
        if text is None:return
        data=bytes.fromhex(text)
        if not data or len(data)>256 or a+len(data)>len(self.doc.data):raise ValueError('จำนวนไบต์ไม่ถูกต้องหรือเกินขอบเขต')
        if mb.askyesno('ยืนยันแก้ไบต์',f'แก้ {len(data)} ไบต์ ที่ 0x{a:X} โดยตรง?\nคำสั่งนี้แก้ไบต์ดิบโดยไม่ใช้สูตรแปลงค่า',parent=self):self.doc.edit_bytes(a,data);self.project_dirty=True;self.render()
    def goto_hex(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        text=sd.askstring('ไปยังตำแหน่ง','ตำแหน่ง HEX:',parent=self)
        if text is None:return
        a=int(text,16)
        if not 0<=a<len(self.doc.data):raise ValueError('ตำแหน่งอยู่นอกไฟล์')
        cols=min(16,len(self.doc.data)-a);rows=min(16,(len(self.doc.data)-a)//cols);self.current=spec(dict(name=f'พื้นที่ไบต์ 0x{a:X}',address=a,rows=rows,cols=cols,bits=8),self.doc);self.grid.selected=set();self.render()
    def diff_csv(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        path=fd.asksaveasfilename(title='ส่งออกรายงานไบต์ที่เปลี่ยน',defaultextension='.csv')
        if not path:return
        ref=self.reference if self.reference is not None else self.doc.original;count=0
        with open(path,'w',newline='',encoding='utf-8-sig') as f:
            writer=csv.writer(f);writer.writerow(['ตำแหน่ง HEX','ไบต์อ้างอิง HEX','ไบต์ปัจจุบัน HEX','ผลต่างฐานสิบ'])
            for i,(a,b) in enumerate(zip(ref,self.doc.data)):
                if a!=b:writer.writerow([f'{i:08X}',f'{a:02X}',f'{b:02X}',b-a]);count+=1
        self.status.set(f'ส่งออกรายงาน {count:,} ไบต์ที่ต่างกันแล้ว')
    def export_patch(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        patch=make_patch(self.doc.original,self.doc.data);path=fd.asksaveasfilename(title='ส่งออกแพตช์ข้อมูลพร้อม SHA-256',defaultextension='.ptspatch')
        if path:Path(path).write_text(json.dumps(patch,indent=2),encoding='utf-8');self.status.set('ส่งออกแพตช์ข้อมูลแล้ว ใช้ได้เฉพาะ BIN ที่ตรงกับ SHA-256 ต้นทาง')
    def import_patch(self):
        if not self.doc.data:raise ValueError('เปิด BIN ก่อน')
        path=fd.askopenfilename(title='นำเข้าแพตช์ข้อมูล PTS',filetypes=[('แพตช์ PTS','*.ptspatch')])
        if not path:return
        if Path(path).stat().st_size>150*1024*1024:raise ValueError('ไฟล์แพตช์ใหญ่เกินกำหนด')
        patch=json.loads(Path(path).read_text(encoding='utf-8'))
        if mb.askyesno('นำเข้าแพตช์ข้อมูล','ตรวจ SHA-256 และใช้แพตช์กับไฟล์ปัจจุบัน? สามารถย้อนกลับได้',parent=self):apply_data_patch(self.doc,patch);self.project_dirty=True;self.render()
    def help(self):
        self.text_window('วิธีใช้งาน PTS Studio 3',HELP)
    def text_window(self,title,text):
        win=tk.Toplevel(self);win.title(title);win.geometry('850x620');box=tk.Text(win,wrap='word',font=('Tahoma',11),padx=20,pady=20,bg=self.theme['bg'],fg=self.theme['fg']);box.pack(fill='both',expand=True);box.insert('end',text);box.config(state='disabled');win.bind('<Escape>',lambda e:win.destroy())

HELP='''เพิ่มในรุ่น 3: นำเข้า XDF XML แบบ stride=0, ตารางและค่าคงที่, integer/float32, row/column-major, สูตรคณิตศาสตร์และสูตรกลับ, อ่านแกน BIN แบบตรงหรือ LABEL, แก้ HEX, ส่งออก/นำเข้าแพตช์ SHA-256 และรายงาน diff CSV\nนำเข้า XDF มีรายงานสิ่งที่ข้าม ไม่ได้รองรับ XDF ทุกแบบ แกนอ้างอิงที่ยังไม่รองรับแสดงเป็นหมายเลขช่องพร้อมรายงาน\n\nPTS STUDIO 3.1 — โปรแกรมแก้ไขไฟล์ที่พัฒนาขึ้นใหม่

เริ่มต้น: ไฟล์ → เปิดตัวอย่างฝึกใช้งาน เพื่อทดลองได้โดยไม่ใช้ BIN ของรถ
เปิด BIN แล้วสร้างนิยามแมป โดยระบุ HEX / ขนาด / บิต / ลำดับไบต์ให้ตรงกับไฟล์
กำหนดตัวคูณ ค่าชดเชย หน่วย และค่าแกนคงที่ได้ การเขียนกลับปัดเป็นค่าดิบจำนวนเต็ม

ตาราง: ลากเมาส์เลือกหลายช่อง หรือ Shift+คลิก เลือกช่วง ดับเบิลคลิก/Enter กำหนดค่า
บวก/ลบ คูณ ปรับเปอร์เซ็นต์ ไล่ค่า และปรับผิว ทำเฉพาะช่องที่เลือก
ไล่ค่าระหว่างจุด = แทรกค่าเชิงเส้นตามหมายเลขช่อง ไม่ได้อิงระยะห่างแกน
ปรับผิว = เฉลี่ยค่าปัจจุบันกับค่าเฉลี่ยเพื่อนบ้าน 4 ทิศในหนึ่งรอบ
คัดลอก/วางเป็นค่าตัวเลขคั่นด้วยแท็บหรือจุลภาค ไม่รวมแกน
ข้อมูลเกินช่วงจำนวนเต็มหรือเกินขอบเขตตารางจะไม่ถูกเขียน
Ctrl+Z ย้อนกลับ / Ctrl+Y ทำซ้ำ การแก้ไขชุดเดียวใช้หนึ่งขั้นย้อนกลับ
มุมสีทอง = ช่องที่ต่างจากต้นฉบับ หรือ BIN อ้างอิงที่เปิดเปรียบเทียบ

F10 = ซ่อนส่วนหัวและรายการแมปเพื่อขยายตาราง F11 = เต็มจอ Esc = ออกจากโหมด
กราฟ 3D เปิดหน้าต่างแยก ลากเพื่อหมุน ล้อเมาส์ซูม Esc หรือ X ปิด
ตารางใหญ่กว่า 32×32 กราฟ 3D ลดความละเอียดการวาด แต่ข้อมูลในตารางยังครบ
ธีมเลือกได้ 3 แบบ เมนู คำอธิบาย และข้อความการทำงานของ PTS เป็นภาษาไทย

โครงการ .pts3 เก็บต้นฉบับ ข้อมูลแก้ไข นิยาม และเวอร์ชันได้ 5 ชุด
ส่งออก BIN ใช้ชื่อใหม่เพื่อเก็บต้นฉบับ การแก้นิยามไม่เปลี่ยนไบต์จนกว่าจะแก้ค่าตาราง
นิยาม JSON เป็นรูปแบบ PTS ที่มีตัวอย่างให้ในชุดซอร์ส
ค้นหาบล็อกที่อาจเป็นแมปเป็นการประเมินความต่อเนื่องอย่างง่าย ไม่ได้ระบุชื่อหรือหน้าที่แมป

ขอบเขตที่ยังไม่มี: ADX/A2L/DAMOS/OLS, ปลั๊กอินเฉพาะผู้ผลิต,
checksum ECU, บันทึกสด/จำลอง/อ่านและแฟลช ECU
ไม่มีการใช้ซอร์สภายในหรือองค์ประกอบโปรแกรม TunerPro/WinOLS และไม่จำเป็นต้องติดตั้งสองโปรแกรมนั้น
ไม่ได้อ้างว่าทำงานเทียบเท่าทุกฟังก์ชันของทั้งสองโปรแกรม
แฮช SHA-256/CRC32 ใช้ตรวจไฟล์เท่านั้น การส่งออก BIN ไม่ยืนยันว่าไฟล์พร้อมเขียนลง ECU
'''

if __name__=='__main__':
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PTS.Studio.3.BlackRed')
    app=Studio()
    if '--smoke-test' in sys.argv:
        def smoke():
            import traceback
            report={'success':False}
            try:
                app.demo();app.update()
                raw=bytes(app.doc.data);app.new_document(Document(raw),None);app.update();assert app.current is None and not app.grid.values
                import tempfile
                xml='<XDFFORMAT><XDFTABLE><title>ตารางจาก XDF</title><description>เก่า</description><XDFAXIS id="x"><indexcount>16</indexcount></XDFAXIS><XDFAXIS id="y"><indexcount>16</indexcount></XDFAXIS><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x400" mmedtypeflags="2" mmedelementsizebits="16" mmedrowcount="16" mmedcolcount="16" mmedmajorstridebits="16" mmedminorstridebits="0"/><MATH equation="X/100"/></XDFAXIS></XDFTABLE></XDFFORMAT>'
                with tempfile.TemporaryDirectory() as tmp:
                    path=Path(tmp)/'legacy_thai.xdf';path.write_bytes(xml.encode('cp874').replace(b'</description>',b'\x90</description>'));app.load_xdf(path,False);app.update();assert app.current['name']=='ตารางจาก XDF' and len(app.grid.values)==256
                app.popup_3d();app.update();app.table_focus();app.update();app.table_focus();app.apply_theme('ดำ–แดง');app.update()
                report={'success':True,'title':app.title(),'cells':len(app.grid.values),'icons':len(app._icons),'graph_window':bool(app.popup.winfo_exists()),'xdf_loaded':bool(app.xdf_path),'legacy_0x90':True,'blank_without_xdf':True}
                if '--capture' in sys.argv:
                    from PIL import ImageGrab
                    ImageGrab.grab().save(os.environ.get('PTS_CAPTURE_PATH','PTS_Studio_preview.png'))
            except Exception:
                report['error']=traceback.format_exc()
            Path(os.environ.get('PTS_SMOKE_REPORT','smoke_report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');app.destroy()
            if not report['success']:sys.exit(1)
        app.after(700,smoke)
    app.mainloop()
