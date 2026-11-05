"""Conservative, independently written XML-XDF subset importer.
Unknown layouts are reported and skipped; BIN bytes are never modified on import.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from engine import spec,raw_values,display_values
from equations import parse,affine
from native_xdf import is_native_xdf,read_native_xdf


def integer(v,default=0):
    if v is None or str(v).strip()=='':return default
    s=str(v).strip();return int(s,16) if s.lower().startswith(('0x','-0x')) else int(s,10)

def decode_xdf(raw,encoding='auto'):
    if len(raw)>16*1024*1024:raise ValueError('XDF ใหญ่เกิน 16 MB')
    declared=re.search(br'<\?xml[^>]*encoding=[\'"]([^\'"]+)',raw[:300],re.I)
    declared=declared.group(1).decode('ascii','replace') if declared else None
    if encoding!='auto':candidates=[encoding]
    elif raw.startswith((b'\xff\xfe',b'\xfe\xff')):candidates=['utf-16']
    elif raw.startswith(b'<\x00'):candidates=['utf-16-le']
    elif raw.startswith(b'\x00<'):candidates=['utf-16-be']
    else:candidates=list(dict.fromkeys(([declared] if declared else [])+['utf-8-sig','cp874','cp1252']))
    for enc in candidates:
        try:
            text=raw.decode(enc)
            return text,enc,0
        except (UnicodeDecodeError,LookupError):pass
    # Windows ANSI files can contain undefined single-byte values in labels.
    # Keep a visible replacement marker rather than crashing or dropping bytes.
    single=[enc for enc in candidates if enc and enc.lower().replace('-','') in ('cp874','windows874','cp1252','windows1252','latin1','iso88591')]
    if not single:raise ValueError('ถอดรหัส XDF ไม่สำเร็จ ลองเลือก Windows-874 หรือ Windows-1252')
    enc=single[0];text=raw.decode(enc,errors='replace');return text,enc,text.count('\ufffd')

def read_xml(raw,encoding='auto',with_info=False):
    native=is_native_xdf(raw)
    if native:raw=read_native_xdf(raw)
    text,used,replaced=decode_xdf(raw,encoding)
    if native:used='XDF ไบนารี → '+used
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('ไม่รองรับ DTD หรือ entity ภายนอกใน XDF')
    text=re.sub(r'(<\?xml[^>]*encoding=)[\'"][^\'"]+[\'"]',r'\1"utf-8"',text,count=1,flags=re.I)
    try:root=ET.fromstring(text)
    except ET.ParseError as exc:raise ValueError('XDF ไม่ใช่ XML ที่อ่านได้ หรือเป็น XDF รุ่นเก่าแบบอื่น: '+str(exc)) from exc
    for el in root.iter():el.tag=el.tag.rsplit('}',1)[-1]
    if root.tag!='XDFFORMAT':raise ValueError('รองรับ XDF แบบ XML XDFFORMAT เท่านั้น')
    return (root,used,replaced) if with_info else root

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
    bits=integer(mem.get('mmedelementsizebits'),integer(defaults.get('datasizeinbits'),8))
    major=integer(mem.get('mmedmajorstridebits'));minor=integer(mem.get('mmedminorstridebits'))
    if major not in (0,bits) or minor!=0:raise ValueError('ยังไม่รองรับ stride แบบเว้นช่วงของรายการนี้')
    return dict(address=integer(mem.get('mmedaddress'))+base,bits=bits,endian='little' if flags&2 else 'big',signed=bool(flags&1),layout='column' if flags&4 else 'row',data_type='float' if flags&0x10000 else 'integer')

def import_xdf(path,doc,encoding='auto'):
    if Path(path).stat().st_size>16*1024*1024:raise ValueError('XDF ใหญ่เกิน 16 MB')
    return parse_xdf(Path(path).read_bytes(),doc,encoding)

def display_text(text):
    text=text or ''
    if any('\u0e00'<=c<='\u0e7f' for c in text):return text
    try:fixed=text.encode('cp1252').decode('cp874')
    except (UnicodeEncodeError,UnicodeDecodeError):return text
    if sum('\u0e00'<=c<='\u0e7f' for c in fixed)>=3:return fixed
    return text

def parse_xdf(raw,doc,encoding='auto'):
    root,used,replaced=read_xml(raw,encoding,True);node_index={integer(n.get('uniqueid')):n for n in root if n.get('uniqueid')};header=root.find('XDFHEADER');defaults={};base=0;categories={};axis_sources={};warnings=[];accepted=[];report=[]
    if header is not None:
        d=header.find('DEFAULTS');defaults=dict(d.attrib) if d is not None else {}
        b=header.find('BASEOFFSET')
        if b is not None:base=integer(b.get('offset'))*(-1 if integer(b.get('subtract')) else 1)
        for cat in header.findall('CATEGORY'):categories[integer(cat.get('index'))+1]=display_text(cat.get('name',''))
    def axis_values(axis,count,name):
        if axis is None:return list(range(count)),name+' ไม่มีนิยาม จึงใช้หมายเลขช่อง'
        labels=axis.findall('LABEL')
        if labels:
            try:
                values={integer(e.get('index')):float(e.get('value')) for e in labels}
                if len(values)==count and all(i in values for i in range(count)):return [values[i] for i in range(count)],None
            except (TypeError,ValueError):pass
        embed=axis.find('embedinfo')
        if embed is not None and integer(embed.get('type'))==3:
            try:
                target=node_index.get(integer(embed.get('linkobjid')))
                if target is None:raise ValueError('ไม่พบตารางแกนที่อ้างอิง')
                z=target.find("XDFAXIS[@id='z']") if target.tag=='XDFTABLE' else target
                mem=z.find('EMBEDDEDDATA');data=storage(mem,defaults,base)
                rows=integer(mem.get('mmedrowcount'),1);cols=integer(mem.get('mmedcolcount'),1)
                if rows*cols!=count:raise ValueError('ขนาดตารางอ้างอิงไม่ตรงกับจำนวนแกน')
                data.update(name=name,rows=rows,cols=cols,factor=1,offset=0,equation=equation(z))
                source=spec(data,doc);axis_sources[name]=source
                return display_values(doc,source),None
            except (ValueError,TypeError,AttributeError,SyntaxError) as exc:return list(range(count)),name+' แกนอ้างอิงอ่านไม่ได้: '+str(exc)
        if embed is not None and integer(embed.get('type'))==2:return list(range(count)),name+' รูปแบบแกนอ้างอิงนี้ยังไม่รองรับ' 
        try:
            data=storage(axis.find('EMBEDDEDDATA'),defaults,base);data.update(name=name,rows=1,cols=count,factor=1,offset=0);data['equation']=equation(axis);return display_values(doc,spec(data,doc)),None
        except (ValueError,TypeError,OverflowError,SyntaxError) as exc:return list(range(count)),name+' ใช้หมายเลขช่อง: '+str(exc)
    for node in root:
        if node.tag not in ('XDFTABLE','XDFCONSTANT','XDFFLAG','XDFPATCH'):continue
        original_title=node.findtext('title') or node.get('name') or node.tag;title=display_text(original_title)
        try:
            if node.tag not in ('XDFTABLE','XDFCONSTANT'):raise ValueError('ยังไม่รองรับ bit flag หรือแพตช์คำสั่งจาก XDF')
            axes={a.get('id'):a for a in node.findall('XDFAXIS')}
            z=axes.get('z') if node.tag=='XDFTABLE' else node
            if z is None:raise ValueError('ไม่มีแกนค่า Z')
            mem=z.find('EMBEDDEDDATA');m=storage(mem,defaults,base)
            x=axes.get('x');y=axes.get('y')
            rows=integer(mem.get('mmedrowcount'),integer(y.findtext('indexcount'),1) if y is not None else 1);cols=integer(mem.get('mmedcolcount'),integer(x.findtext('indexcount'),1) if x is not None else 1)
            if node.tag=='XDFCONSTANT':rows=cols=1
            for axis,key in [('x','cols'),('y','rows')]:
                ax=axes.get(axis)
                n=integer(ax.findtext('indexcount'),0) if ax is not None else 0
                current=cols if key=='cols' else rows
                if n and n!=current:raise ValueError('จำนวนแกนไม่ตรงกับขนาดที่ระบุใน EMBEDDEDDATA')
            eq=equation(z);m.update(name=title,source_name=original_title,description=display_text(node.findtext('description')),rows=rows,cols=cols,unit=display_text(z.findtext('units')),factor=1,offset=0,equation=eq,xdf_id=node.get('uniqueid',''))
            notes=[];axis_sources.clear()
            for key,ax,count in [('x_axis',axes.get('x'),cols),('y_axis',axes.get('y'),rows)]:
                values,note=axis_values(ax,count,key);m[key]=values
                if note:notes.append(note)
            m['axis_sources']=dict(axis_sources)
            cats=[categories.get(integer(c.get('category')),'') for c in node.findall('CATEGORYMEM')];m['category']=' / '.join(c for c in cats if c)
            try:
                a,b=affine(eq)
                if not a:raise ValueError('สูตรเป็นค่าคงที่')
            except ValueError:
                m['read_only']=True;m['read_only_reason']='สูตรไม่เป็นเชิงเส้น ต้องกำหนดและตรวจสูตรแปลงกลับก่อน';notes.append(m['read_only_reason'])
            m=spec(m,doc);display_values(doc,m);accepted.append(m);report.append('รับแล้ว: '+title+(' [อ่านอย่างเดียว]' if m.get('read_only') else '')+''.join('\n  '+n for n in notes))
        except (ValueError,TypeError,OverflowError,KeyError,SyntaxError,ET.ParseError) as exc:report.append('ข้าม: '+title+' — '+str(exc))
    if not report:raise ValueError('ไม่พบตารางหรือค่าคงที่ใน XDF')
    locations={}
    for m in accepted:
        region=(m['address'],m['rows']*m['cols']*m['bits']//8)
        if region in locations:report.append('ข้อมูลตำแหน่งร่วม: '+m['name']+' ใช้ไบต์เดียวกับ '+locations[region])
        else:locations[region]=m['name']
    info=f'รหัสอักขระ: {used}'
    if header is not None:
        title=header.findtext('deftitle') or ''
        if title:report.append('ชื่อภายใน XDF: '+display_text(title).strip())
    if replaced:info+=f' • อักขระในข้อความที่อ่านไม่ได้แทนด้วย � จำนวน {replaced} ตัว กรุณาตรวจชื่อและคำอธิบาย หรือเลือกรหัสอักขระเอง'
    return accepted,report+[info]
