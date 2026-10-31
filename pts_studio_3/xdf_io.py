"""Conservative, independently written XML-XDF subset importer.
Unknown layouts are reported and skipped; BIN bytes are never modified on import.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from engine import spec,raw_values,display_values
from equations import parse,affine


def integer(v,default=0):
    if v is None or str(v).strip()=='':return default
    s=str(v).strip();return int(s,16) if s.lower().startswith(('0x','-0x')) else int(s,10)

def read_xml(raw):
    if len(raw)>16*1024*1024:raise ValueError('XDF ใหญ่เกิน 16 MB')
    if raw.startswith((b'\xff\xfe',b'\xfe\xff')):text=raw.decode('utf-16')
    else:
        declared=re.search(br'<\?xml[^>]*encoding=[\'"]([^\'"]+)',raw[:300],re.I)
        enc=declared.group(1).decode('ascii') if declared else 'utf-8-sig'
        try:text=raw.decode(enc)
        except UnicodeDecodeError:
            if declared:raise ValueError('รหัสอักขระ XDF ไม่ตรงกับที่ประกาศ')
            text=raw.decode('cp1252')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('ไม่รองรับ DTD หรือ entity ภายนอกใน XDF')
    text=re.sub(r'(<\?xml[^>]*encoding=)[\'"][^\'"]+[\'"]',r'\1"utf-8"',text,count=1,flags=re.I)
    root=ET.fromstring(text)
    for el in root.iter():el.tag=el.tag.rsplit('}',1)[-1]
    if root.tag!='XDFFORMAT':raise ValueError('รองรับ XDF แบบ XML XDFFORMAT เท่านั้น')
    return root

def equation(node):
    maths=node.findall('MATH')
    if not maths:return 'X'
    if len(maths)!=1:raise ValueError('ยังไม่รองรับสูตรแยกตามช่อง แถว หรือคอลัมน์')
    math=maths[0]
    if any(k not in ('equation',) for k in math.attrib):raise ValueError('ยังไม่รองรับสูตรที่มีขอบเขตเฉพาะ')
    for var in math.findall('VAR'):
        if var.get('id','X').upper()!='X' or any(k not in ('id',) for k in var.attrib):raise ValueError('ยังไม่รองรับตัวแปรอ้างอิงภายนอกในสูตร')
    eq=math.get('equation','X');parse(eq);return eq

def storage(mem,defaults,base):
    if mem is None or mem.get('mmedaddress') is None:raise ValueError('ไม่มีตำแหน่งไบนารีโดยตรง')
    flags=integer(mem.get('mmedtypeflags'),None)
    if flags is None:
        flags=(2 if integer(defaults.get('lsbfirst'),1) else 0)|(1 if integer(defaults.get('signed')) else 0)|(0x10000 if integer(defaults.get('float')) else 0)
    if flags&~0x10007:raise ValueError('ธงชนิดข้อมูล XDF นี้ยังไม่รองรับ')
    for key in ('mmedmajorstridebits','mmedminorstridebits'):
        if integer(mem.get(key))!=0:raise ValueError('รุ่นนี้รับ XDF ที่ stride เป็น 0 เท่านั้น')
    bits=integer(mem.get('mmedelementsizebits'),integer(defaults.get('datasizeinbits'),8))
    return dict(address=integer(mem.get('mmedaddress'))+base,bits=bits,endian='little' if flags&2 else 'big',signed=bool(flags&1),layout='column' if flags&4 else 'row',data_type='float' if flags&0x10000 else 'integer')

def import_xdf(path,doc):
    if Path(path).stat().st_size>16*1024*1024:raise ValueError('XDF ใหญ่เกิน 16 MB')
    return parse_xdf(Path(path).read_bytes(),doc)

def parse_xdf(raw,doc):
    root=read_xml(raw);header=root.find('XDFHEADER');defaults={};base=0;categories={};warnings=[];accepted=[];report=[]
    if header is not None:
        d=header.find('DEFAULTS');defaults=dict(d.attrib) if d is not None else {}
        b=header.find('BASEOFFSET')
        if b is not None:base=integer(b.get('offset'))*(-1 if integer(b.get('subtract')) else 1)
        for cat in header.findall('CATEGORY'):categories[integer(cat.get('index'))+1]=cat.get('name','')
    def axis_values(axis,count,name):
        if axis is None:return list(range(count)),name+' ไม่มีนิยาม จึงใช้หมายเลขช่อง'
        labels=axis.findall('LABEL')
        if labels:
            try:
                values={integer(e.get('index')):float(e.get('value')) for e in labels}
                if len(values)==count and all(i in values for i in range(count)):return [values[i] for i in range(count)],None
            except (TypeError,ValueError):pass
        embed=axis.find('embedinfo')
        if embed is not None and integer(embed.get('type')) in (2,3):return list(range(count)),name+' อ้างอิงนิยามอื่น จึงใช้หมายเลขช่อง'
        try:
            data=storage(axis.find('EMBEDDEDDATA'),defaults,base);data.update(name=name,rows=1,cols=count,factor=1,offset=0);data['equation']=equation(axis);return display_values(doc,spec(data,doc)),None
        except (ValueError,TypeError,OverflowError,SyntaxError) as exc:return list(range(count)),name+' ใช้หมายเลขช่อง: '+str(exc)
    for node in root:
        if node.tag not in ('XDFTABLE','XDFCONSTANT','XDFFLAG','XDFPATCH'):continue
        title=node.findtext('title') or node.get('name') or node.tag
        try:
            if node.tag not in ('XDFTABLE','XDFCONSTANT'):raise ValueError('ยังไม่รองรับ bit flag หรือแพตช์คำสั่งจาก XDF')
            axes={a.get('id'):a for a in node.findall('XDFAXIS')}
            z=axes.get('z') if node.tag=='XDFTABLE' else node
            if z is None:raise ValueError('ไม่มีแกนค่า Z')
            mem=z.find('EMBEDDEDDATA');m=storage(mem,defaults,base)
            rows=integer(mem.get('mmedrowcount'),1);cols=integer(mem.get('mmedcolcount'),1)
            if node.tag=='XDFCONSTANT':rows=cols=1
            for axis,key in [('x','cols'),('y','rows')]:
                ax=axes.get(axis)
                n=integer(ax.findtext('indexcount'),0) if ax is not None else 0
                current=cols if key=='cols' else rows
                if n and n!=current:raise ValueError('จำนวนแกนไม่ตรงกับขนาดที่ระบุใน EMBEDDEDDATA')
            eq=equation(z);m.update(name=title,description=node.findtext('description') or '',rows=rows,cols=cols,unit=z.findtext('units') or '',factor=1,offset=0,equation=eq,xdf_id=node.get('uniqueid',''))
            notes=[]
            for key,ax,count in [('x_axis',axes.get('x'),cols),('y_axis',axes.get('y'),rows)]:
                values,note=axis_values(ax,count,key);m[key]=values
                if note:notes.append(note)
            cats=[categories.get(integer(c.get('category')),'') for c in node.findall('CATEGORYMEM')];m['category']=' / '.join(c for c in cats if c)
            try:
                a,b=affine(eq)
                if not a:raise ValueError('สูตรเป็นค่าคงที่')
            except ValueError:
                m['read_only']=True;m['read_only_reason']='สูตรไม่เป็นเชิงเส้น ต้องกำหนดและตรวจสูตรแปลงกลับก่อน';notes.append(m['read_only_reason'])
            m=spec(m,doc);display_values(doc,m);accepted.append(m);report.append('รับแล้ว: '+title+(' [อ่านอย่างเดียว]' if m.get('read_only') else '')+''.join('\n  '+n for n in notes))
        except (ValueError,TypeError,OverflowError,KeyError,SyntaxError,ET.ParseError) as exc:report.append('ข้าม: '+title+' — '+str(exc))
    if not report:raise ValueError('ไม่พบตารางหรือค่าคงที่ใน XDF')
    return accepted,report
