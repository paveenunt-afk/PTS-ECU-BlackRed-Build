import os, json, threading, queue, datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
from serial.tools import list_ports
from PIL import Image, ImageTk

THEMES={"PTS ดำแดง":("#151515","#b71927","#ffffff"),"น้ำเงิน":("#101e34","#2860ad","#ffffff"),"เขียว":("#10271c","#25875d","#ffffff"),"สว่าง":("#eef1f5","#526781","#192334")}
CONFIG=Path(os.getenv("APPDATA") or Path.home())/"PTS_Honda_KLine"/"settings.json"
class App:
 def __init__(self,root):
  self.root=root;root.title("PTS Honda K-Line v0.2 | Real Serial I/O");root.geometry("1020x690")
  try:self.settings=json.loads(CONFIG.read_text(encoding="utf-8"))
  except Exception:self.settings={}
  self.theme=tk.StringVar(value=self.settings.get("theme","PTS ดำแดง"));self.com=tk.StringVar();self.baud=tk.StringVar(value="10400");self.cmd=tk.StringVar();self.status=tk.StringVar(value="ยังไม่เปิดพอร์ต")
  self.serial=None;self.alive=False;self.events=queue.Queue();self.bgimg=None;self.logoimg=None
  self.header=tk.Frame(root);self.header.pack(fill="x")
  self.logo=tk.Label(self.header);self.logo.pack(side="left",padx=8)
  self.heading=tk.Label(self.header,text="PTS HONDA K-LINE  •  REAL I/O",font=("Segoe UI",17,"bold"));self.heading.pack(side="left",padx=8,pady=10)
  ttk.Button(self.header,text="ธีม / โลโก้ / พื้นหลัง",command=self.customize).pack(side="right",padx=12)
  self.body=tk.Frame(root);self.body.pack(fill="both",expand=True,padx=12,pady=10)
  self.bglabel=tk.Label(self.body);self.bglabel.place(relx=0,rely=0,relwidth=1,relheight=1)
  self.toolbar=tk.Frame(self.body);self.toolbar.pack(fill="x",pady=5)
  self.combox=ttk.Combobox(self.toolbar,textvariable=self.com,width=28,state="readonly");self.combox.pack(side="left")
  ttk.Button(self.toolbar,text="ค้นหาพอร์ต",command=self.refresh).pack(side="left",padx=4)
  ttk.Combobox(self.toolbar,textvariable=self.baud,values=["9600","10400","19200","38400","57600","115200"],width=9).pack(side="left",padx=5)
  ttk.Button(self.toolbar,text="เชื่อมต่อ",command=self.connect).pack(side="left",padx=4)
  ttk.Button(self.toolbar,text="ตัดการเชื่อมต่อ",command=self.disconnect).pack(side="left",padx=4)
  self.statlabel=tk.Label(self.body,textvariable=self.status,anchor="w");self.statlabel.pack(fill="x",pady=6)
  self.sendrow=tk.Frame(self.body);self.sendrow.pack(fill="x")
  ttk.Entry(self.sendrow,textvariable=self.cmd).pack(side="left",fill="x",expand=True)
  ttk.Button(self.sendrow,text="ส่ง HEX",command=self.send).pack(side="left",padx=5)
  ttk.Button(self.sendrow,text="บันทึก Log",command=self.save_log).pack(side="left",padx=5)
  self.log=tk.Text(self.body,font=("Consolas",11),wrap="word");self.log.pack(fill="both",expand=True,pady=8)
  self.note=tk.Label(self.body,text="เปิด COM สำเร็จ ไม่ได้ยืนยันว่า ECU ตอบกลับ | ต้องใช้ K-Line transceiver ที่เหมาะสม ไม่ต่อ FT232RL เข้าสาย 12V โดยตรง",wraplength=940);self.note.pack(fill="x")
  self.refresh();self.apply_theme();root.after(80,self.drain);root.protocol("WM_DELETE_WINDOW",self.close)
 def save(self):
  CONFIG.parent.mkdir(parents=True,exist_ok=True);CONFIG.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding="utf-8")
 def apply_theme(self):
  bg,accent,fg=THEMES.get(self.theme.get(),THEMES["PTS ดำแดง"])
  for widget in [self.root,self.body,self.toolbar,self.sendrow]:widget.configure(bg=bg)
  self.header.configure(bg=accent)
  for widget in [self.logo,self.heading]:widget.configure(bg=accent,fg="white")
  for widget in [self.statlabel,self.note]:widget.configure(bg=bg,fg=fg)
  self.log.configure(bg="#0c0e12" if self.theme.get()!="สว่าง" else "white",fg="#e9eef3" if self.theme.get()!="สว่าง" else "#17212b",insertbackground=fg)
  for key,widget,limit in [("logo",self.logo,(95,45)),("background",self.bglabel,(1100,700))]:
   try:
    path=self.settings.get(key)
    if not path:widget.configure(image="");continue
    im=Image.open(path);im.thumbnail(limit)
    photo=ImageTk.PhotoImage(im);widget.configure(image=photo);widget.image=photo
   except Exception:widget.configure(image="")
  self.bglabel.lower()
 def customize(self):
  win=tk.Toplevel(self.root);win.title("ปรับแต่ง PTS");win.geometry("380x220")
  ttk.Label(win,text="เลือกธีม").pack(pady=8)
  ttk.Combobox(win,textvariable=self.theme,values=list(THEMES),state="readonly").pack()
  def choose(key):
   path=filedialog.askopenfilename(parent=win,filetypes=[("รูปภาพ","*.png *.jpg *.jpeg *.webp *.bmp")])
   if path:self.settings[key]=path;self.apply_theme();self.save()
  ttk.Button(win,text="เลือกรูปโลโก้",command=lambda:choose("logo")).pack(pady=8)
  ttk.Button(win,text="เลือกรูปพื้นหลัง",command=lambda:choose("background")).pack(pady=8)
  ttk.Button(win,text="บันทึกธีม",command=lambda:(self.settings.update(theme=self.theme.get()),self.save(),self.apply_theme(),win.destroy())).pack(pady=8)
 def refresh(self):
  ports=[f"{p.device}  {p.description}" for p in list_ports.comports()]
  self.combox["values"]=ports
  if ports:self.com.set(ports[0])
 def connect(self):
  if self.serial:return
  try:
   name=self.com.get().split("  ")[0];self.serial=serial.Serial(name,int(self.baud.get()),timeout=0.1)
   self.alive=True;self.status.set("เปิดพอร์ต "+name+" สำเร็จ (ยังไม่ยืนยัน ECU)")
   threading.Thread(target=self.reader,daemon=True).start()
  except Exception as e:self.serial=None;messagebox.showerror("เชื่อมต่อไม่ได้",str(e))
 def reader(self):
  while self.alive:
   try:
    data=self.serial.read(1024)
    if data:self.events.put(("RX",data.hex(" ").upper()))
   except Exception as e:self.events.put(("ERROR",str(e)));break
 def drain(self):
  while not self.events.empty():
   typ,msg=self.events.get_nowait();self.write_log(typ,msg)
  self.root.after(80,self.drain)
 def write_log(self,typ,msg):
  self.log.insert("end",f"{datetime.datetime.now():%H:%M:%S.%f}"[:-3]+f" [{typ}] {msg}\n");self.log.see("end")
 def send(self):
  if not self.serial:messagebox.showwarning("ยังไม่เชื่อมต่อ","เปิดพอร์ต COM ก่อน");return
  try:
   data=bytes.fromhex(self.cmd.get());self.serial.write(data);self.write_log("TX",data.hex(" ").upper())
  except Exception as e:messagebox.showerror("ส่งไม่ได้",str(e))
 def save_log(self):
  path=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("Text","*.txt")])
  if path:Path(path).write_text(self.log.get("1.0","end"),encoding="utf-8")
 def disconnect(self):
  self.alive=False
  if self.serial:
   try:self.serial.close()
   except Exception:pass
  self.serial=None;self.status.set("ตัดการเชื่อมต่อแล้ว")
 def close(self):self.disconnect();self.root.destroy()
if __name__=="__main__":
 root=tk.Tk();App(root);root.mainloop()
