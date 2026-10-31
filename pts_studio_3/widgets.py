import math
import tkinter as tk
from tkinter import ttk

THEMES={
 'ดำ–แดง':dict(bg='#0d1119',panel='#171d29',fg='#e6ecf7',muted='#929fb5',accent='#ff425b',cell0=(25,46,68),cell1=(221,48,66)),
 'กรมท่า–ฟ้า':dict(bg='#0b1324',panel='#14233b',fg='#e2f1ff',muted='#8ea9c7',accent='#38bdf8',cell0=(21,43,72),cell1=(25,141,188)),
 'เทา–ทอง':dict(bg='#171719',panel='#252529',fg='#f4efdf',muted='#aaa89d',accent='#e6b450',cell0=(45,45,52),cell1=(167,119,33))}

def color(t,v):
    v=max(0,min(1,v)); a=t['cell0']; b=t['cell1'];return '#'+''.join(f'{round(x+(y-x)*v):02x}' for x,y in zip(a,b))
def number(v):return f'{v:.5g}'

class HeatGrid(ttk.Frame):
    def __init__(self,parent,select,edit,theme):
        super().__init__(parent); self.theme=theme; self.onselect=select; self.onedit=edit; self.values=[]; self.selected=set(); self.anchor=None; self.cursor=0; self.spec=None; self.changed=set(); self.cw=88; self.ch=36; self.pending=None
        self.canvas=tk.Canvas(self,highlightthickness=0,takefocus=True,bg=theme['bg']); self.canvas.grid(row=0,column=0,sticky='nsew'); self.rowconfigure(0,weight=1); self.columnconfigure(0,weight=1)
        sx=ttk.Scrollbar(self,orient='horizontal',command=self.xview); sx.grid(row=1,column=0,sticky='ew'); sy=ttk.Scrollbar(self,orient='vertical',command=self.yview); sy.grid(row=0,column=1,sticky='ns'); self.canvas.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
        self.canvas.bind('<Configure>',lambda e:self.queue()); self.canvas.bind('<Button-1>',self.click); self.canvas.bind('<B1-Motion>',self.drag); self.canvas.bind('<Double-1>',lambda e:self.onedit()); self.canvas.bind('<Return>',lambda e:self.onedit()); self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-4>',lambda e:self.yview('scroll',-3,'units')); self.canvas.bind('<Button-5>',lambda e:self.yview('scroll',3,'units'))
        for key,dr,dc in [('Left',0,-1),('Right',0,1),('Up',-1,0),('Down',1,0)]:self.canvas.bind('<'+key+'>',lambda e,r=dr,c=dc:self.move(r,c,e.state&1))
    def xview(self,*args):self.canvas.xview(*args);self.queue()
    def yview(self,*args):self.canvas.yview(*args);self.queue()
    def wheel(self,e):
        if e.state&4:self.zoom(1 if e.delta>0 else -1)
        else:self.yview('scroll',-3 if e.delta>0 else 3,'units')
        return 'break'
    def zoom(self,n):self.cw=max(50,min(180,self.cw+8*n));self.ch=max(26,min(62,self.ch+3*n));self.queue()
    def set_data(self,values,spec,changed=()):
        self.values=list(values); self.spec=spec; self.changed=set(changed); self.selected={i for i in self.selected if i<len(values)}
        if not self.selected and values:self.selected={0};self.anchor=0;self.cursor=0
        self.queue();self.onselect()
    def queue(self):
        if self.pending:self.after_cancel(self.pending)
        self.pending=self.after(10,self.draw)
    def index_at(self,e):
        if not self.spec:return None
        c=int((self.canvas.canvasx(e.x)-65)//self.cw);r=int((self.canvas.canvasy(e.y)-36)//self.ch)
        return r*self.spec['cols']+c if 0<=r<self.spec['rows'] and 0<=c<self.spec['cols'] else None
    def click(self,e):
        i=self.index_at(e);self.canvas.focus_set()
        if i is None:return
        self.cursor=i
        if e.state&1 and self.anchor is not None:self.rectangle(i)
        else:self.anchor=i;self.selected={i}
        self.queue();self.onselect()
    def rectangle(self,i):
        cols=self.spec['cols']; r,c=divmod(i,cols);ar,ac=divmod(self.anchor,cols)
        self.selected={rr*cols+cc for rr in range(min(r,ar),max(r,ar)+1) for cc in range(min(c,ac),max(c,ac)+1)}
    def drag(self,e):
        i=self.index_at(e)
        if i is not None and self.anchor is not None:self.cursor=i;self.rectangle(i);self.queue();self.onselect()
    def move(self,dr,dc,extend):
        if not self.values:return
        cols=self.spec['cols'];i=self.cursor if self.cursor<len(self.values) else 0;r,c=divmod(i,cols);r=max(0,min(self.spec['rows']-1,r+dr));c=max(0,min(cols-1,c+dc));i=r*cols+c;self.cursor=i
        if extend and self.anchor is not None:self.rectangle(i)
        else:self.selected={i};self.anchor=i
        self.queue();self.onselect()
        return 'break'
    def all(self):self.selected=set(range(len(self.values)));self.anchor=0;self.queue();self.onselect()
    def draw(self):
        self.pending=None;c=self.canvas;c.delete('all');t=self.theme;c.configure(bg=t['bg'])
        if not self.spec or not self.values:c.create_text(35,45,anchor='nw',text='เปิด BIN แล้วเลือก XDF เพื่ออ่านรายการแมปและตาราง',fill=t['muted'],font=('Tahoma',14));return
        rows=self.spec['rows'];cols=self.spec['cols'];c.configure(scrollregion=(0,0,65+cols*self.cw,36+rows*self.ch))
        left=c.canvasx(0);top=c.canvasy(0);width=c.winfo_width();height=c.winfo_height();c0=max(0,int((left-65)//self.cw));c1=min(cols,int((left+width-65)//self.cw)+2);r0=max(0,int((top-36)//self.ch));r1=min(rows,int((top+height-36)//self.ch)+2);lo=min(self.values);span=max(self.values)-lo or 1
        for col in range(c0,c1):
            x=65+col*self.cw;c.create_rectangle(x,0,x+self.cw,36,fill=t['panel'],outline=t['bg']);c.create_text(x+self.cw/2,18,text=number(self.spec['x_axis'][col]),fill=t['muted'],font=('Consolas',10))
        for row in range(r0,r1):
            y=36+row*self.ch;c.create_rectangle(0,y,65,y+self.ch,fill=t['panel'],outline=t['bg']);c.create_text(32,y+self.ch/2,text=number(self.spec['y_axis'][row]),fill=t['muted'],font=('Consolas',10))
            for col in range(c0,c1):
                i=row*cols+col;x=65+col*self.cw;v=self.values[i];selected=i in self.selected
                c.create_rectangle(x+1,y+1,x+self.cw-1,y+self.ch-1,fill=color(t,(v-lo)/span),outline='#ffffff' if selected else t['bg'],width=2 if selected else 1)
                c.create_text(x+self.cw/2,y+self.ch/2,text=number(v),fill='#ffffff',font=('Consolas',11,'bold' if selected else 'normal'))
                if i in self.changed:c.create_polygon(x+self.cw-10,y+3,x+self.cw-3,y+3,x+self.cw-3,y+10,fill='#ffe28c')

class Graph(tk.Canvas):
    def __init__(self,parent,theme,mode='3d'):
        super().__init__(parent,bg=theme['bg'],highlightthickness=0);self.theme=theme;self.mode=mode;self.values=[];self.spec=None;self.angle=.65;self.elev=.45;self.zoom=1;self.last=None
        self.bind('<Configure>',lambda e:self.draw());self.bind('<Button-1>',lambda e:setattr(self,'last',(e.x,e.y)));self.bind('<B1-Motion>',self.drag);self.bind('<MouseWheel>',self.wheel)
    def set_data(self,values,spec):self.values=list(values);self.spec=spec;self.draw()
    def drag(self,e):
        if self.last:self.angle+=(e.x-self.last[0])*.012;self.elev=max(.1,min(1,(self.elev+(e.y-self.last[1])*.004)))
        self.last=(e.x,e.y);self.draw()
    def wheel(self,e):self.zoom=max(.4,min(2,self.zoom*(1.1 if e.delta>0 else .9)));self.draw()
    def draw(self):
        self.delete('all');t=self.theme;self.config(bg=t['bg']);w=max(300,self.winfo_width());h=max(240,self.winfo_height())
        if not self.values or not self.spec:return
        vals=self.values;lo=min(vals);hi=max(vals);span=hi-lo or 1
        if self.mode=='2d':
            for j in range(6):
                y=45+j*(h-85)/5;self.create_line(55,y,w-25,y,fill=t['panel']);self.create_text(48,y,text=number(hi-span*j/5),anchor='e',fill=t['muted'],font=('Consolas',9))
            cols=self.spec['cols']
            for row in range(self.spec['rows']):
                pts=[]
                for col in range(cols):pts.extend((60+col*(w-90)/max(1,cols-1),h-40-(vals[row*cols+col]-lo)/span*(h-85)))
                if len(pts)>2:self.create_line(*pts,fill=color(t,row/max(1,self.spec['rows']-1)),width=2)
                elif pts:self.create_oval(pts[0]-3,pts[1]-3,pts[0]+3,pts[1]+3,fill=t['accent'])
        else:
            rows=self.spec['rows'];cols=self.spec['cols'];scale=min(w*.8,h)*.72*self.zoom
            def point(r,c):
                x=c/max(1,cols-1)-.5;y=r/max(1,rows-1)-.5;z=(vals[r*cols+c]-lo)/span
                return (w*.5+scale*(x*math.cos(self.angle)-y*math.sin(self.angle)),h*.65+scale*self.elev*(x*math.sin(self.angle)+y*math.cos(self.angle))-scale*.52*z)
            rs=list(range(0,rows,max(1,math.ceil(rows/32))));cs=list(range(0,cols,max(1,math.ceil(cols/32))))
            if rs[-1]!=rows-1:rs.append(rows-1)
            if cs[-1]!=cols-1:cs.append(cols-1)
            polys=[]
            for ra,rb in zip(rs,rs[1:]):
                for ca,cb in zip(cs,cs[1:]):
                    corners=[(ra,ca),(ra,cb),(rb,cb),(rb,ca)]; pts=[point(r,c) for r,c in corners];z=sum(vals[r*cols+c] for r,c in corners)/4;depth=sum((c/max(1,cols-1)-.5)*math.sin(self.angle)+(r/max(1,rows-1)-.5)*math.cos(self.angle) for r,c in corners)
                    polys.append((depth,pts,z))
            for _,pts,z in sorted(polys,key=lambda item:item[0]):self.create_polygon(*[n for pt in pts for n in pt],fill=color(t,(z-lo)/span),outline='#4a5263',width=1)
            if rows==1 or cols==1:
                points=[point(i//cols,i%cols) for i in range(len(vals))]
                if len(points)>1:self.create_line(*[n for pt in points for n in pt],fill=t['accent'],width=3)
                else:self.create_oval(points[0][0]-4,points[0][1]-4,points[0][0]+4,points[0][1]+4,fill=t['accent'])
        self.create_text(18,18,text=self.spec['name']+'   '+self.spec['unit']+f'   [{number(lo)} … {number(hi)}]',anchor='nw',fill=t['fg'],font=('Tahoma',12,'bold'))
        self.create_text(18,h-16,text='ลากเมาส์เพื่อหมุน • ล้อเมาส์เพื่อซูม' if self.mode=='3d' else 'แต่ละเส้นแทนหนึ่งแถวของตาราง',anchor='w',fill=t['muted'],font=('Tahoma',10))
