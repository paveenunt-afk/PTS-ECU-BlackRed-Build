"""PTS's independently implemented binary/map workspace. No ECU I/O."""
import base64
import binascii
import hashlib
import json
import math
import zlib
import struct
from equations import calculate,parse,affine
from pathlib import Path
from core import Document

MAX_FILE=32*1024*1024

def checked_bytes(path):
    p=Path(path)
    if not 0<p.stat().st_size<=MAX_FILE:raise ValueError('ไฟล์ต้องมีขนาด 1 ไบต์ ถึง 32 MB')
    return p.read_bytes()

def spec(value,doc):
    m=dict(value)
    for key,default in [('name','แมปใหม่'),('unit',''),('endian','little')]:m[key]=str(m.get(key,default))
    for key,default in [('address',0),('rows',16),('cols',16),('bits',16)]:m[key]=int(m.get(key,default))
    m['signed']=m.get('signed',False)
    if type(m['signed']) is not bool:raise ValueError('ค่า signed ต้องเป็น true หรือ false')
    m['factor']=float(m.get('factor',1)); m['offset']=float(m.get('offset',0))
    if not math.isfinite(m['factor']) or not math.isfinite(m['offset']) or m['factor']==0:raise ValueError('ตัวคูณต้องไม่เป็นศูนย์ และค่าการแปลงต้องเป็นจำนวนจำกัด')
    if m['bits'] not in (8,16,32) or m['endian'] not in ('little','big'):raise ValueError('รูปแบบข้อมูลไม่รองรับ')
    m['data_type']=str(m.get('data_type','integer'))
    m['layout']=str(m.get('layout','row'))
    if m['data_type'] not in ('integer','float') or m['layout'] not in ('row','column'):raise ValueError('รูปแบบข้อมูลไม่รองรับ')
    if m['data_type']=='float' and m['bits']!=32:raise ValueError('รองรับทศนิยม IEEE754 ขนาด 32 บิตเท่านั้น')
    if not 1<=m['rows']<=128 or not 1<=m['cols']<=128:raise ValueError('ขนาดตารางไม่ถูกต้อง')
    raw_values(doc,m)
    if m.get('equation'):parse(m['equation'])
    if m.get('inverse'):parse(m['inverse'])
    for key,count in [('x_axis',m['cols']),('y_axis',m['rows'])]:
        axis=m.get(key, list(range(count)))
        if not isinstance(axis,list) or len(axis)!=count:raise ValueError('จำนวนค่าของแกนไม่ตรงกับตาราง')
        axis=[float(v) for v in axis]
        if not all(math.isfinite(v) for v in axis):raise ValueError('ค่าแกนไม่ถูกต้อง')
        m[key]=axis
    return m

def params(m):return {k:m[k] for k in ('address','rows','cols','bits','endian','signed')}
def addresses(m):
    size=m['bits']//8
    return [m['address']+(r*m['cols']+c if m.get('layout','row')=='row' else c*m['rows']+r)*size for r in range(m['rows']) for c in range(m['cols'])]
def raw_values(doc,m):
    size=m['bits']//8; positions=addresses(m)
    if min(positions)<0 or max(positions)+size>len(doc.data):raise ValueError('ตารางอยู่นอกขอบเขตไฟล์')
    vals=[]
    for a in positions:
        blob=doc.data[a:a+size]
        v=struct.unpack(('<' if m['endian']=='little' else '>')+'f',blob)[0] if m.get('data_type')=='float' else int.from_bytes(blob,m['endian'],signed=m['signed'])
        if not math.isfinite(v):raise ValueError('ตารางมีค่า NaN หรือ Infinity ที่รุ่นนี้ไม่รองรับ')
        vals.append(v)
    return vals
def display_values(doc,m):
    vals=raw_values(doc,m)
    return [calculate(m['equation'],v) if m.get('equation') else v*m['factor']+m['offset'] for v in vals]
def raw_from_display(v,m):
    if m.get('read_only'):raise ValueError('แมปนี้อ่านอย่างเดียว: '+str(m.get('read_only_reason','ยังไม่มีสูตรแปลงกลับที่ยืนยันได้')))
    v=float(v)
    if not math.isfinite(v):raise ValueError('ค่าต้องเป็นจำนวนจำกัด')
    if m.get('equation'):
        if m.get('inverse'):result=calculate(m['inverse'],v)
        else:
            factor,offset=affine(m['equation'])
            if not factor:raise ValueError('สูตรคงที่แปลงกลับไม่ได้')
            result=(v-offset)/factor
    else:result=(v-m['offset'])/m['factor']
    if m.get('data_type')=='float':
        blob=struct.pack(('<' if m['endian']=='little' else '>')+'f',result)
        result=struct.unpack(('<' if m['endian']=='little' else '>')+'f',blob)[0]
        if not math.isfinite(result):raise ValueError('ค่าทศนิยมล้นช่วง')
    else:
        result=round(result);result.to_bytes(m['bits']//8,m['endian'],signed=m['signed'])
    if m.get('equation'):
        actual=calculate(m['equation'],result)
        # An explicit inverse must return the same domain/branch. Allow quantization.
        if m.get('inverse') and not math.isclose(actual,v,rel_tol=1e-5,abs_tol=max(1e-5,abs(calculate(m['equation'],result+1)-actual)*.51 if m.get('data_type')!='float' else 1e-5)):
            raise ValueError('สูตรแปลงกลับให้ผลไม่ตรงกับสูตรแสดงค่า')
    return result

def change_cells(doc,m,updates):
    if m.get('read_only'):raise ValueError('แมปนี้อ่านอย่างเดียว: '+str(m.get('read_only_reason','ยังไม่มีสูตรแปลงกลับ')))
    values=raw_values(doc,m)
    for index,value in updates.items():
        if type(index) is not int or not 0<=index<len(values):raise ValueError('ช่องอยู่นอกตาราง')
        values[index]=raw_from_display(value,m)
    size=m['bits']//8;start=m['address'];blob=bytearray(doc.data[start:start+len(values)*size])
    for a,v in zip(addresses(m),values):
        encoded=struct.pack(('<' if m['endian']=='little' else '>')+'f',v) if m.get('data_type')=='float' else int(v).to_bytes(size,m['endian'],signed=m['signed'])
        blob[a-start:a-start+size]=encoded
    doc.edit_bytes(start,blob)

def restore_raw_cells(doc,m,indices):
    if m.get('read_only'):raise ValueError('แมปนี้อ่านอย่างเดียว')
    positions=addresses(m);size=m['bits']//8;start=m['address'];blob=bytearray(doc.data[start:start+len(positions)*size])
    for i in indices:
        if type(i) is not int or not 0<=i<len(positions):raise ValueError('ช่องอยู่นอกตาราง')
        a=positions[i];blob[a-start:a-start+size]=doc.original[a:a+size]
    doc.edit_bytes(start,blob)

def interpolate(values,rows,cols,selected,axis):
    result={}; selected=set(selected)
    lines=([r*cols+c for c in range(cols)] for r in range(rows)) if axis=='x' else ([r*cols+c for r in range(rows)] for c in range(cols))
    for line in lines:
        cells=[i for i in line if i in selected]
        if len(cells)<3:continue
        first,last=cells[0],cells[-1]; start=line.index(first); span=line.index(last)-start
        for i in cells:result[i]=values[first]+(values[last]-values[first])*(line.index(i)-start)/span
    if not result:raise ValueError('เลือกอย่างน้อย 3 ช่องในแถวหรือคอลัมน์เดียวกัน')
    return result

def smooth(values,rows,cols,selected):
    result={}
    for i in selected:
        r,c=divmod(i,cols); near=[values[rr*cols+cc] for rr,cc in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)) if 0<=rr<rows and 0<=cc<cols]
        if near:result[i]=(values[i]+sum(near)/len(near))/2
    return result

def pack_project(doc,maps,versions):
    return dict(format='PTS_STUDIO_3',original=base64.b64encode(doc.original).decode(),modified=base64.b64encode(doc.data).decode(),maps=maps,versions=versions)

def save_project(path,doc,maps,versions):
    payload=json.dumps(pack_project(doc,maps,versions),ensure_ascii=False).encode('utf-8')
    target=Path(path); temp=target.with_name(target.name+'.tmp'); temp.write_bytes(zlib.compress(payload)); temp.replace(target)

def load_project(path):
    # Limit expanded JSON before parsing an untrusted project.
    p=Path(path)
    if not 0<p.stat().st_size<=350*1024*1024:raise ValueError('ขนาดไฟล์โครงการไม่ถูกต้อง')
    packed=p.read_bytes(); dec=zlib.decompressobj(); data=dec.decompress(packed,350*1024*1024+1)
    if len(data)>350*1024*1024 or not dec.eof or dec.unused_data:raise ValueError('โครงการใหญ่เกินกำหนดหรือเสียหาย')
    obj=json.loads(data)
    if obj.get('format') not in ('PTS_STUDIO_2','PTS_STUDIO_3'):raise ValueError('รูปแบบโครงการไม่ถูกต้อง')
    original=base64.b64decode(obj['original'],validate=True); modified=base64.b64decode(obj['modified'],validate=True)
    if len(original)!=len(modified) or not 0<len(original)<=MAX_FILE:raise ValueError('ขนาดไฟล์ในโครงการไม่ถูกต้อง')
    doc=Document(original); doc.data=bytearray(modified); maps=[spec(m,doc) for m in obj['maps']]
    versions=obj.get('versions',[])
    if len(versions)>5:raise ValueError('จำนวนเวอร์ชันเกินกำหนด')
    for version in versions:
        raw=base64.b64decode(version['data'],validate=True)
        if len(raw)!=len(original):raise ValueError('ขนาดเวอร์ชันไม่ถูกต้อง')
        version['name']=str(version['name'])
    return doc,maps,versions

def candidate_regions(doc,bits=16,endian='little',width=16):
    """Rank smooth nonconstant blocks; never claim identification of ECU maps."""
    size=bits//8; count=width*width; block=count*size; result=[]
    if bits not in (8,16,32) or width not in (8,16):raise ValueError('พารามิเตอร์ค้นหาไม่ถูกต้อง')
    for address in range(0,min(len(doc.data),2*1024*1024)-block+1,block):
        vals=doc.values(address,width,width,bits,endian,False); span=max(vals)-min(vals)
        if span==0 or len(set(vals))<8:continue
        jumps=[abs(vals[r*width+c+1]-vals[r*width+c]) for r in range(width) for c in range(width-1)]
        score=1-sum(jumps)/len(jumps)/span
        if score>.90:result.append((score,address))
    return sorted(result,reverse=True)[:100]
