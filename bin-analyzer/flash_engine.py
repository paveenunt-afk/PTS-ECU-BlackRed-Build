"""Experimental MEN-E21 FTDI K-Line adapter for roccofz1/HondaECU.
GPL-3.0. See vendor/LICENSE and SOURCES.txt. Not tested with an ECU.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import time

PART = '38770-MEN-E21'
SIZE = 262144
CHECKSUM = 0x1FFFA


def validate_rom(data):
    if len(data) != SIZE:
        raise ValueError(f'{PART}: ต้องมีขนาด {SIZE} bytes เท่านั้น')
    expected = (-sum(data[:CHECKSUM] + data[CHECKSUM+1:])) & 255
    if data[CHECKSUM] != expected:
        raise ValueError(f'ECU checksum ไม่ผ่าน: stored={data[CHECKSUM]:02X}, calculated={expected:02X}')
    return hashlib.sha256(data).hexdigest()


def receive_exact(dev, size, deadline):
    result = bytearray()
    while len(result) < size:
        if time.monotonic() >= deadline:
            raise TimeoutError('หมดเวลารอคำตอบ ECU')
        chunk = dev._read(size-len(result))
        if chunk:
            result.extend(chunk)
        else:
            time.sleep(.001)
    return result


def exchange(dev, mtype, data):
    # Frame construction and checksum from the bundled GPL upstream.
    payload = list(mtype) + [len(mtype)+len(data)+2] + list(data)
    payload.append((-sum(payload)) & 255)
    packet = bytes(payload)
    dev.flush()
    written = dev._write(packet)
    if written is not None and written != len(packet):
        raise OSError('ส่งข้อมูลไม่ครบ')
    deadline = time.monotonic() + 2
    if bytes(receive_exact(dev, len(packet), deadline)) != packet:
        raise ValueError('K-Line echo ไม่ตรงกับข้อมูลที่ส่ง')
    head = receive_exact(dev, len(mtype)+1, deadline)
    length = head[-1]
    if not len(head)+1 <= length <= 255:
        raise ValueError('ความยาวเฟรมตอบกลับไม่ถูกต้อง')
    response = head + receive_exact(dev, length-len(head), deadline)
    if sum(response) & 255:
        raise ValueError('Checksum เฟรมตอบกลับไม่ผ่าน')
    if response == packet:
        raise ValueError('ได้รับ echo แทนคำตอบ ECU')
    # Upstream does not document a full semantic ACK table. ROM readback is
    # mandatory after writing; a short response alone never means success.
    ml = len(mtype)
    return response[:ml], response[ml:ml+1], response[ml+1:-1], length-ml-2


def read_rom(ecu, output):
    path = Path(output)
    # Exclusive creation prevents overwriting a backup or a source file.
    with path.open('xb') as f:
        for address in range(0, SIZE, 8):
            info = ecu.send_command([0x82, 0x82, 0],
                [address//65536] + list(struct.pack('<H', address%65536)) + [8])
            if len(info[2]) != 8:
                raise ValueError(f'อ่านข้อมูลไม่ครบที่ 0x{address:X}; ไฟล์ที่เหลือเป็นข้อมูลไม่สมบูรณ์')
            f.write(info[2])
            if address % 8192 == 0:
                print(f'อ่าน {address:,}/{SIZE:,} bytes', flush=True)
    data = path.read_bytes()
    validate_rom(data)
    return data


def authenticate_read(ecu):
    ecu.send_command([0x27], [0xe0,0x48,0x65,0x6c,0x6c,0x6f,0x48,0x6f])
    ecu.send_command([0x27], [0xe0,0x77,0x41,0x72,0x65,0x59,0x6f,0x75])


def load_driver():
    spec = importlib.util.spec_from_file_location('honda_upstream', Path(__file__).parent/'vendor'/'HondaECU.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class CheckedECU(mod.HondaECU):
        def send_command(self, mtype, data=None, retries=0, debug=False):
            if time.monotonic() > self.operation_deadline:
                raise TimeoutError('หมดเวลาทำรายการ หยุดส่งคำสั่งแล้ว')
            return exchange(self.dev, mtype, data or [])

        def init(self, debug=False):
            self._break(.070)
            time.sleep(.130)
            self.dev.flush()
            info = self.send_command([0xfe], [0x72])
            return len(info[2]) == 1 and info[2][0] == 0x72

    return mod, CheckedECU


def main():
    parser = argparse.ArgumentParser(description='ทดลอง Honda MEN-E21 / FTDI K-Line เท่านั้น')
    parser.add_argument('mode', choices=['read','write'])
    parser.add_argument('file', type=Path)
    parser.add_argument('--part', required=True, choices=[PART])
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    target = args.file.resolve()
    if args.mode == 'read' and target.exists():
        raise ValueError('ชื่อไฟล์ปลายทางมีอยู่แล้ว เลือกชื่อใหม่')
    if args.mode == 'write':
        source = target.read_bytes()
        validate_rom(source)
        if not args.backup:
            raise ValueError('ต้องระบุ --backup สำหรับสำรองจากกล่องก่อนลบ')
        backup = args.backup.resolve()
        verification = backup.with_name(backup.name+'.readback.bin')
        if backup.exists() or verification.exists() or target in (backup, verification):
            raise ValueError('เลือกชื่อสำรองและ readback ที่ยังไม่มีอยู่')
    mod, cls = load_driver()
    devices = mod.Driver().list_devices()
    if len(devices) != 1:
        raise ValueError(f'ต้องพบ FTDI เพียง 1 ตัว แต่พบ {len(devices)} ตัว')
    ecu = cls(device_id=devices[0][2])
    ecu.operation_deadline = time.monotonic()+1800
    try:
        ecu.setup()
        print('เริ่มเชื่อมต่อกล่องที่เปิดไฟเลี้ยงแล้ว', flush=True)
        if not ecu.init():
            raise ValueError('ECU ไม่ตอบรับ init; ยังไม่เริ่มลบ ROM')
        ecu.send_command([0x72],[0x00,0xf0])
        authenticate_read(ecu)
        if args.mode == 'read':
            read_rom(ecu, target)
            print('อ่านครบและตรวจ checksum ผ่าน', flush=True)
            return
        print('อ่านสำรองจากกล่องก่อนลบ', flush=True)
        original = read_rom(ecu, backup)
        # Do not infer ECU identity from the firmware filename or a user label.
        # Restrict this prototype to the MEN-E21 reference supplied with the app.
        reference_sha256 = 'f100797699934904c48f3d86a5e7e67826be6ae7998729bc1797decae2030694'
        if hashlib.sha256(original).hexdigest() != reference_sha256:
            raise ValueError('ROM ในกล่องไม่ตรงกับ MEN-E21 อ้างอิงทุกไบต์ จึงหยุดก่อนลบ')
        print('เริ่มเขียน ROM — รักษาไฟเลี้ยงและการเชื่อมต่อ', flush=True)
        ecu.do_init_write()
        # No automatic fallback to recovery after an unexpected response.
        ecu.do_erase()
        mod.do_write_flash(ecu, bytearray(source))
        ecu.do_post_write()
        print('ส่งข้อมูลจบ กำลังตรวจอ่านกลับ; ยังไม่ถือว่าสำเร็จ', flush=True)
        if not ecu.init():
            raise ValueError('เริ่มอ่านกลับไม่ได้ สถานะการเขียนยังไม่ยืนยัน')
        ecu.send_command([0x72],[0x00,0xf0])
        authenticate_read(ecu)
        actual = read_rom(ecu, verification)
        if actual != source:
            raise ValueError('อ่านกลับไม่ตรงกับไฟล์ที่เขียน สถานะการเขียนไม่ผ่าน')
        print('เขียนสำเร็จ: อ่านกลับตรงกันทุกไบต์', flush=True)
    finally:
        if ecu.dev is not None:
            ecu.dev.close()
            ecu.dev = None


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'หยุดทำงาน: {exc}', flush=True)
        raise SystemExit(1)
