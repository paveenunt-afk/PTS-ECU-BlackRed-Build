import unittest
from core import Document
from xdf_io import parse_xdf,decode_xdf
from engine import display_values

XML='<XDFFORMAT><XDFTABLE><title>ตารางทดสอบ</title><description>ข้อความ</description><XDFAXIS id="x"><indexcount>2</indexcount></XDFAXIS><XDFAXIS id="y"><indexcount>2</indexcount></XDFAXIS><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0" mmedtypeflags="2" mmedelementsizebits="16" mmedmajorstridebits="16" mmedminorstridebits="0"/><MATH equation="X/10"/></XDFAXIS></XDFTABLE></XDFFORMAT>'
class LegacyTests(unittest.TestCase):
    def doc(self):return Document(b'\x0a\x00\x14\x00\x1e\x00\x28\x00')
    def test_windows_thai_undefined_byte_reproduces_screenshot(self):
        raw=XML.encode('cp874').replace(b'</description>',b'\x90</description>');d=self.doc();maps,report=parse_xdf(raw,d)
        self.assertEqual(maps[0]['name'],'ตารางทดสอบ');self.assertEqual(display_values(d,maps[0]),[1,2,3,4]);self.assertEqual(d.data,d.original);self.assertIn('cp874',report[-1]);self.assertIn('1 ตัว',report[-1])
    def test_declared_cp1252_undefined(self):
        raw=b'<?xml version="1.0" encoding="windows-1252"?>'+XML.replace('ตารางทดสอบ','Map').replace('ข้อความ','old').encode('ascii').replace(b'old',b'old\x90');maps,report=parse_xdf(raw,self.doc());self.assertEqual(len(maps),1);self.assertIn('windows-1252',report[-1])
    def test_user_selected_encoding(self):
        maps,report=parse_xdf(XML.encode('cp874'),self.doc(),'cp874');self.assertEqual(maps[0]['name'],'ตารางทดสอบ');self.assertIn('cp874',report[-1])
    def test_utf16_with_and_without_bom(self):
        for enc in ('utf-16','utf-16-le','utf-16-be'):
            maps,_=parse_xdf(XML.encode(enc),self.doc());self.assertEqual(maps[0]['name'],'ตารางทดสอบ')
    def test_utf8_and_derived_dimensions(self):
        maps,_=parse_xdf(XML.encode(),self.doc());self.assertEqual((maps[0]['rows'],maps[0]['cols']),(2,2))
    def test_bad_numeric_metadata_is_skipped(self):
        raw=XML.encode('cp874').replace(b'mmedaddress="0"',b'mmedaddress="\x90"');maps,report=parse_xdf(raw,self.doc());self.assertEqual(maps,[]);self.assertTrue(report[0].startswith('ข้าม'))
if __name__=='__main__':unittest.main()
