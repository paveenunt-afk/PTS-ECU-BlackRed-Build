"""Native XDF compatibility for files readable without an opening password.
Original containers and edit-password metadata are never rewritten.
"""
MAGIC=b'\x05\x22\x97\x00'
HEADER_BYTES=264
_READ_KEY=bytes.fromhex('c10a3da7a973d73b25a1ff023efe9058')

def is_native_xdf(data):return data.startswith(MAGIC)

def _stream(data,key):
    # RC4 stream transform, implemented here to avoid runtime DLL dependencies.
    state=list(range(256));j=0
    for i in range(256):
        j=(j+state[i]+key[i%len(key)])&255;state[i],state[j]=state[j],state[i]
    i=j=0;out=bytearray(len(data))
    for pos,value in enumerate(data):
        i=(i+1)&255;j=(j+state[i])&255;state[i],state[j]=state[j],state[i]
        out[pos]=value^state[(state[i]+state[j])&255]
    return bytes(out)

def read_native_xdf(data):
    if not is_native_xdf(data):raise ValueError('ไม่ใช่ XDF ไบนารีที่รองรับ')
    if not HEADER_BYTES<len(data)<=16*1024*1024:raise ValueError('ขนาด XDF ไบนารีไม่ถูกต้อง')
    if data[131]!=100:raise ValueError('XDF นี้ต้องใช้รหัสเปิดไฟล์ ตัวอ่านนี้รองรับเฉพาะ XDF ที่เปิดอ่านได้โดยไม่ใช้รหัส')
    payload=_stream(data[HEADER_BYTES:],_READ_KEY)
    if b'<XDFFORMAT' not in payload[:4096]:raise ValueError('XDF ไบนารีเป็นรูปแบบที่ยังไม่รองรับหรือข้อมูลเสียหาย')
    return payload
