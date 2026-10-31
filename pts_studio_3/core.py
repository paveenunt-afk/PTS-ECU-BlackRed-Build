import json, math, hashlib, zlib
from pathlib import Path

class Document:
    def __init__(self, data=b''):
        self.original=bytes(data); self.data=bytearray(data); self.undo_stack=[]; self.redo_stack=[]
    def values(self, address, rows, cols, bits=16, endian='little', signed=False):
        width=bits//8
        if bits not in (8,16,32) or not 1<=rows<=128 or not 1<=cols<=128: raise ValueError('ขนาดตารางไม่ถูกต้อง')
        if address<0 or address+rows*cols*width>len(self.data): raise ValueError('ตารางอยู่นอกขอบเขตไฟล์')
        return [int.from_bytes(self.data[p:p+width],endian,signed=signed) for p in range(address,address+rows*cols*width,width)]
    def edit(self, address, values, bits=16, endian='little', signed=False):
        width=bits//8; new=b''.join(int(v).to_bytes(width,endian,signed=signed) for v in values)
        if address<0 or address+len(new)>len(self.data): raise ValueError('ตำแหน่งอยู่นอกไฟล์')
        old=bytes(self.data[address:address+len(new)])
        if old!=new:
            self.undo_stack.append((address,old,new)); self.redo_stack.clear(); self.data[address:address+len(new)]=new
    def edit_bytes(self, address, new):
        new=bytes(new)
        if address<0 or address+len(new)>len(self.data):raise ValueError('ตำแหน่งอยู่นอกไฟล์')
        old=bytes(self.data[address:address+len(new)])
        if old!=new:
            self.undo_stack.append((address,old,new));self.redo_stack.clear();self.data[address:address+len(new)]=new
    def undo(self):
        if self.undo_stack:
            a,old,new=self.undo_stack.pop(); self.data[a:a+len(old)]=old; self.redo_stack.append((a,old,new))
    def redo(self):
        if self.redo_stack:
            a,old,new=self.redo_stack.pop(); self.data[a:a+len(new)]=new; self.undo_stack.append((a,old,new))
    def hashes(self):
        return f'SHA-256: {hashlib.sha256(self.data).hexdigest()}\nCRC32: {zlib.crc32(self.data):08X}'
    def differences(self, other):
        return [(i,self.data[i] if i<len(self.data) else None,other[i] if i<len(other) else None) for i in range(max(len(self.data),len(other))) if (self.data[i] if i<len(self.data) else None)!=(other[i] if i<len(other) else None)]

def validate_map(m, doc):
    m=dict(m); m['name']=str(m.get('name','แมป')); m['address']=int(m['address']); m['rows']=int(m['rows']); m['cols']=int(m['cols']); m['bits']=int(m.get('bits',16)); m['endian']=m.get('endian','little'); m['signed']=bool(m.get('signed',False))
    if m['endian'] not in ('little','big'): raise ValueError('ลำดับไบต์ไม่ถูกต้อง')
    doc.values(m['address'],m['rows'],m['cols'],m['bits'],m['endian'],m['signed']); return m
