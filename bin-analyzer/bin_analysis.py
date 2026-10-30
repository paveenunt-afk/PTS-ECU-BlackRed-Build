"""Offline BIN inspection. Evidence candidates are never flash instructions."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
LIMIT = 64*1024*1024
# Search templates from the user's examples; these are not validated ECU commands.
TEMPLATES = {
    'user_wakeup_example': bytes.fromhex('FE 04 72 8C'),
    'user_id_example': bytes.fromhex('80 04 10 80 14'),
    'user_programming_example': bytes.fromhex('80 04 10 85 19'),
    'user_reset_example': bytes.fromhex('80 03 11 01 95'),
}


def catalog():
    result=[]
    for number,line in enumerate((BASE/'ecu_catalog.tsv').read_text(encoding='utf-8-sig').splitlines(),1):
        if not line.strip():continue
        cells=[s.strip() for s in line.strip().split('\t')]
        if len(cells)!=7:raise ValueError(f'ตาราง ID บรรทัด {number} ต้องมี 7 คอลัมน์')
        sid,part,model,a,b,kib,vendor=cells
        if not re.fullmatch('[0-9A-Fa-f]{10}',sid):raise ValueError(f'ID บรรทัด {number} ไม่ถูกต้อง')
        result.append(dict(software_id=sid.upper(),part=part,model=model,
                           raw_value_1=a,raw_value_2=b,size_kib=int(kib),vendor=vendor))
    return result


def entropy(data):
    if not data:return 0.0
    length=len(data)
    return round(-sum((n/length)*math.log2(n/length) for n in Counter(data).values()),4)


def occurrences(data,needle,limit=32):
    positions=[];start=0
    while len(positions)<limit:
        pos=data.find(needle,start)
        if pos<0:break
        positions.append(pos);start=pos+1
    return positions


def inspect(path):
    path=Path(path)
    with path.open('rb') as stream:data=stream.read(LIMIT+1)
    if not data or len(data)>LIMIT:raise ValueError('รองรับไฟล์ 1 byte ถึง 64 MiB')
    records=catalog()
    hits=[]
    for item in records:
        for kind,needle in [('binary_5byte_id',bytes.fromhex(item['software_id'])),
                            ('ascii_software_id',item['software_id'].encode('ascii'))]:
            pos=occurrences(data,needle)
            if pos:hits.append(dict(record=item,kind=kind,offsets=pos,
                                    confirmed_ecu_identity=False))
    strings=[];string_count=0
    # Walk all printable runs without retaining an unbounded list in memory.
    for match in re.finditer(rb'[\x20-\x7e]{6,}',data):
        string_count+=1
        if len(strings)<200:
            strings.append(dict(offset=match.start(),length=match.end()-match.start(),
                                text=match.group()[:240].decode('ascii')))
    part_hits=[]
    for match in re.finditer(rb'(?:387[07]0|30400)-[A-Z0-9]{3,4}-[A-Z0-9]{3}(?:-[A-Z0-9-]+)?',data):
        if len(part_hits)>=100:break
        part_hits.append(dict(offset=match.start(),text=match.group()[:100].decode('ascii')))
    patterns=[]
    for name,needle in TEMPLATES.items():
        offsets=occurrences(data,needle)
        if offsets:patterns.append(dict(template=name,hex=needle.hex(' ').upper(),offsets=offsets,
            interpretation='byte sequence match only; not proof of a diagnostic command'))
    # Relative names are hints, never used to choose a flash profile.
    normalized=re.sub('[^A-Z0-9]','',str(path).upper())
    name_hints=[r for r in records if re.sub('[^A-Z0-9]','',r['part'].upper()) in normalized]
    sizes=[r for r in records if r['size_kib']*1024==len(data)]
    region_size=max(4096,math.ceil(len(data)/256/4096)*4096)
    regions=[]
    for start in range(0,len(data),region_size):
        chunk=data[start:start+region_size]
        regions.append(dict(offset=start,length=len(chunk),entropy=entropy(chunk),
                            zero_percent=round(100*chunk.count(0)/len(chunk),2),
                            ff_percent=round(100*chunk.count(255)/len(chunk),2)))
    return dict(file=str(path),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
        entropy=entropy(data),size_candidates_count=len(sizes),filename_hints=name_hints,
        embedded_part_candidates=part_hits,software_id_candidates=hits,
        template_byte_matches=patterns,ascii_strings=strings,ascii_run_count=string_count,
        strings_truncated=string_count>len(strings),regions=regions,
        capabilities=dict(file_inspected=True,cpu_architecture='unknown',
            flash_protocol_extracted=False,seed_key_recovered=False,
            flash_compatibility='not established',automatic_hardware_commands=False))


def report_text(report):
    lines=['PTS BIN Analyzer 3.0',f"ไฟล์: {report['file']}",
        f"ขนาด: {report['size_bytes']:,} bytes",f"SHA-256: {report['sha256']}",
        f"Entropy: {report['entropy']} bits/byte (ไม่ใช่หลักฐานว่ามีการเข้ารหัส)",
        'สถานะ: วิเคราะห์ไฟล์ออฟไลน์ ยังไม่ทราบสถาปัตยกรรม CPU/โปรโตคอลแฟลช',
        'ค่าในตาราง ID ไม่มีหัวคอลัมน์ครบ จึงเก็บค่า 1/ค่า 2 ตามต้นฉบับ',
        '\nข้อมูลอ้างอิงจากชื่อไฟล์ (ยังไม่ยืนยันกล่อง):']
    for item in report['filename_hints']:
        lines.append(f"  {item['software_id']} | {item['part']} | {item['model']} | {item['size_kib']} KiB")
    if not report['filename_hints']:lines.append('  ไม่พบชื่อที่ตรงตาราง')
    lines.append('\nข้อความหมายเลขชิ้นส่วนในไฟล์:')
    for item in report['embedded_part_candidates']:lines.append(f"  0x{item['offset']:X}: {item['text']}")
    if not report['embedded_part_candidates']:lines.append('  ไม่พบ')
    lines.append('\nไบต์รหัสตรงตาราง ID (อาจเป็นข้อมูลที่บังเอิญตรง ไม่ยืนยันรุ่น ECU):')
    for item in report['software_id_candidates']:
        lines.append(f"  {item['record']['software_id']} | {item['kind']} | "+', '.join(f'0x{x:X}' for x in item['offsets']))
    if not report['software_id_candidates']:lines.append('  ไม่พบ')
    lines.append('\nตำแหน่งตรงกับไบต์ตัวอย่างผู้ใช้ (ยังไม่ยืนยันว่าเป็นคำสั่งที่ถูกเรียกใช้):')
    for item in report['template_byte_matches']:lines.append(f"  {item['hex']}: "+', '.join(f'0x{x:X}' for x in item['offsets']))
    if not report['template_byte_matches']:lines.append('  ไม่พบ')
    lines.append(f"\nข้อความ ASCII (แสดง {len(report['ascii_strings'])} จาก {report['ascii_run_count']} ช่วง):")
    for item in report['ascii_strings']:lines.append(f"  0x{item['offset']:X} ({item['length']} bytes): {item['text']}")
    lines.extend(['\nข้อจำกัด:','การพบไบต์/ข้อความไม่พิสูจน์ว่าเป็นคำสั่งแฟลชหรือสูตร Seed/Key',
        'Disassembly แสดงคำสั่ง CPU ตามสถาปัตยกรรมที่ผู้ใช้เลือก ไม่ได้แปลงเป็นโปรโตคอล K-Line',
        'อ่าน–เขียนจริงมีเฉพาะโค้ด MEN-E21 รุ่นทดลองเดิม ยังไม่ผ่านทดสอบกับ ECU จริง'])
    return '\n'.join(lines)


def available_architectures():
    try:import capstone as cs
    except ImportError:return {}
    names={
        'ARM little-endian':('CS_ARCH_ARM','CS_MODE_ARM',False),
        'Thumb little-endian':('CS_ARCH_ARM','CS_MODE_THUMB',False),
        'ARM64 little-endian':('CS_ARCH_ARM64','CS_MODE_LITTLE_ENDIAN',False),
        'MIPS32 big-endian':('CS_ARCH_MIPS','CS_MODE_MIPS32',True),
        'PowerPC32 big-endian':('CS_ARCH_PPC','CS_MODE_32',True),
        'SuperH SH4 big-endian':('CS_ARCH_SH','CS_MODE_SH4',True),
    }
    result={}
    for name,(arch,mode,big) in names.items():
        if not hasattr(cs,arch) or not hasattr(cs,mode):continue
        a=getattr(cs,arch);m=getattr(cs,mode)|(cs.CS_MODE_BIG_ENDIAN if big else 0)
        try:cs.Cs(a,m)
        except cs.CsError:continue
        result[name]=(a,m)
    return result


def disassemble(path,architecture,file_offset,base_address,byte_count=256):
    if file_offset<0 or base_address<0 or not 1<=byte_count<=4096:raise ValueError('Offset/Address หรือจำนวนไบต์ไม่ถูกต้อง')
    choices=available_architectures()
    if architecture not in choices:raise ValueError('ยังไม่มี Capstone หรือไม่รองรับสถาปัตยกรรมนี้')
    import capstone as cs
    with Path(path).open('rb') as f:
        f.seek(file_offset);data=f.read(byte_count)
    if not data:raise ValueError('Offset อยู่นอกไฟล์')
    engine=cs.Cs(*choices[architecture])
    instructions=[]
    for instruction in engine.disasm(data,base_address+file_offset):
        instructions.append(f'{instruction.address:08X}  {instruction.bytes.hex(" "):24}  {instruction.mnemonic} {instruction.op_str}')
    if not instructions:return 'ถอดคำสั่งไม่ได้ที่ตำแหน่งนี้ อาจเลือก CPU/ตำแหน่ง/รูปแบบไบต์ไม่ตรง'
    consumed=sum(i.size for i in engine.disasm(data,base_address+file_offset))
    return ('สถาปัตยกรรมตามที่ผู้ใช้เลือก — ยังไม่ยืนยันว่าตรงกับ BIN\n'
            'ผลนี้เป็นคำสั่ง CPU ไม่ใช่คำสั่งอ่าน–เขียน ECU\n'+
            '\n'.join(instructions)+f'\nถอดได้ {consumed}/{len(data)} bytes; ส่วนที่เหลือไม่ได้ตีความ')


def main():
    p=argparse.ArgumentParser(description='วิเคราะห์ BIN ออฟไลน์ ไม่ส่งข้อมูลไป ECU')
    p.add_argument('bin',type=Path);p.add_argument('--json',type=Path);p.add_argument('--text',type=Path)
    a=p.parse_args();r=inspect(a.bin)
    for dest in [a.json,a.text]:
        if dest and dest.resolve()==a.bin.resolve():p.error('ห้ามเขียนทับไฟล์ต้นฉบับ')
    if a.json:
        with a.json.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
    if a.text:
        with a.text.open('x',encoding='utf-8') as f:f.write(report_text(r))
    if not a.json and not a.text:print(report_text(r))

if __name__=='__main__':main()
