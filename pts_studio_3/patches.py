import hashlib

def digest(data):return hashlib.sha256(data).hexdigest()
def make_patch(original,modified):
    if len(original)!=len(modified):raise ValueError('ขนาดไฟล์ไม่เท่ากัน')
    runs=[];start=None
    for i,(a,b) in enumerate(zip(original,modified)):
        if a!=b and start is None:start=i
        if a==b and start is not None:
            runs.append(dict(address=start,before=bytes(original[start:i]).hex(),after=bytes(modified[start:i]).hex()));start=None
        if len(runs)>100000:raise ValueError('แพตช์มีช่วงย่อยมากเกิน 100,000 ช่วง')
    if start is not None:runs.append(dict(address=start,before=bytes(original[start:]).hex(),after=bytes(modified[start:]).hex()))
    return dict(format='PTS_DATA_PATCH_1',size=len(original),base_sha256=digest(original),target_sha256=digest(modified),runs=runs)

def apply_patch(doc,patch):
    if patch.get('format')!='PTS_DATA_PATCH_1' or patch.get('size')!=len(doc.data):raise ValueError('รูปแบบหรือขนาดแพตช์ไม่ตรงกับไฟล์')
    if digest(doc.data)!=patch.get('base_sha256'):raise ValueError('SHA-256 ของไฟล์ปัจจุบันไม่ตรงกับไฟล์ต้นทางของแพตช์')
    runs=patch.get('runs')
    if not isinstance(runs,list) or len(runs)>100000:raise ValueError('จำนวนช่วงแพตช์ไม่ถูกต้อง')
    modified=bytearray(doc.data);last_end=0
    for run in runs:
        a=run['address'];before=bytes.fromhex(run['before']);after=bytes.fromhex(run['after'])
        if type(a) is not int or not before or len(before)!=len(after) or a<last_end or a+len(before)>len(modified):raise ValueError('ช่วงแพตช์ซ้อนทับหรืออยู่นอกไฟล์')
        if bytes(modified[a:a+len(before)])!=before:raise ValueError('ข้อมูลก่อนแก้ไม่ตรงกับแพตช์')
        modified[a:a+len(after)]=after;last_end=a+len(after)
    if digest(modified)!=patch.get('target_sha256'):raise ValueError('ผลแพตช์ไม่ตรงกับ SHA-256 ปลายทาง')
    doc.edit_bytes(0,modified)
