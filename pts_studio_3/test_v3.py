import base64,json,struct,tempfile,unittest
from pathlib import Path
from core import Document
from engine import spec,display_values,change_cells,raw_from_display,restore_raw_cells
from equations import calculate,affine
from xdf_io import parse_xdf
from patches import make_patch,apply_patch

XML='''<?xml version="1.0" encoding="utf-8"?><XDFFORMAT version="1.60"><XDFHEADER><BASEOFFSET offset="4096" subtract="1"/><DEFAULTS datasizeinbits="16" signed="0" lsbfirst="1"/></XDFHEADER><XDFTABLE uniqueid="1"><title>ตารางทดสอบ</title><XDFAXIS id="x"><indexcount>2</indexcount><LABEL index="0" value="1000"/><LABEL index="1" value="2000"/></XDFAXIS><XDFAXIS id="y"><indexcount>2</indexcount><LABEL index="0" value="10"/><LABEL index="1" value="20"/></XDFAXIS><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x1000" mmedtypeflags="0x02" mmedelementsizebits="16" mmedrowcount="2" mmedcolcount="2" mmedmajorstridebits="0" mmedminorstridebits="0"/><units>unit</units><MATH equation="X/100"><VAR id="X"/></MATH></XDFAXIS></XDFTABLE></XDFFORMAT>'''
class V3Tests(unittest.TestCase):
    def doc(self):return Document(b''.join(i.to_bytes(2,'little') for i in [100,200,300,400]))
    def test_xdf_linear_edit_and_axes(self):
        d=self.doc();maps,report=parse_xdf(XML.encode(),d);self.assertEqual(len(maps),1);m=maps[0];self.assertEqual(display_values(d,m),[1,2,3,4]);self.assertEqual(m['x_axis'],[1000,2000]);change_cells(d,m,{1:4.5});self.assertEqual(d.data[2:4],(450).to_bytes(2,'little'));d.undo();self.assertEqual(d.data,d.original)
    def test_xdf_readonly_non_linear(self):
        d=self.doc();maps,_=parse_xdf(XML.replace('X/100','X*X').encode(),d);m=maps[0];self.assertTrue(m['read_only']);before=bytes(d.data)
        with self.assertRaises(ValueError):change_cells(d,m,{0:1})
        self.assertEqual(bytes(d.data),before)
    def test_xdf_unknown_stride_skipped(self):
        maps,report=parse_xdf(XML.replace('mmedmajorstridebits="0"','mmedmajorstridebits="128"').encode(),self.doc());self.assertEqual(maps,[]);self.assertIn('stride',report[0])
    def test_xdf_big_endian(self):
        d=Document(b'\x00\x64\x00\xc8\x01\x2c\x01\x90');maps,_=parse_xdf(XML.replace('mmedtypeflags="0x02"','mmedtypeflags="0x00"').encode(),d);self.assertEqual(display_values(d,maps[0]),[1,2,3,4])
    def test_xdf_dtype_default(self):
        maps,_=parse_xdf(XML.replace(' mmedtypeflags="0x02"','').encode(),self.doc());self.assertEqual(display_values(self.doc(),maps[0]),[1,2,3,4])
    def test_xdf_column_major(self):
        d=self.doc();maps,_=parse_xdf(XML.replace('mmedtypeflags="0x02"','mmedtypeflags="0x06"').encode(),d);m=maps[0];self.assertEqual(display_values(d,m),[1,3,2,4]);change_cells(d,m,{1:9});self.assertEqual(d.data[4:6],(900).to_bytes(2,'little'));self.assertEqual(d.data[:4],d.original[:4])
    def test_xdf_memory_axis(self):
        xml=XML.replace('<LABEL index="0" value="1000"/><LABEL index="1" value="2000"/>','<EMBEDDEDDATA mmedaddress="0x1004" mmedtypeflags="0x02" mmedelementsizebits="16"/><embedinfo type="1"/><MATH equation="X*10"><VAR id="X"/></MATH>');maps,_=parse_xdf(xml.encode(),self.doc());self.assertEqual(maps[0]['x_axis'],[3000,4000])
    def test_xdf_reject_entity(self):
        with self.assertRaises(ValueError):parse_xdf(b'<!DOCTYPE a [<!ENTITY x "bad">]><XDFFORMAT/>',self.doc())
    def test_xdf_constant(self):
        xml='<XDFFORMAT><XDFCONSTANT><title>scalar</title><EMBEDDEDDATA mmedaddress="0" mmedtypeflags="2" mmedelementsizebits="16"/><MATH equation="X+10"/></XDFCONSTANT></XDFFORMAT>';maps,_=parse_xdf(xml.encode(),self.doc());self.assertEqual(display_values(self.doc(),maps[0]),[110])
    def test_expression_boundaries(self):
        self.assertEqual(affine('(X*2+4)/4'),(.5,1));self.assertEqual(calculate('X^2',3),9)
        for code in ('__import__("os")','X.__class__','[X]','X**9999','Y+1'):
            with self.assertRaises((ValueError,SyntaxError)):calculate(code,1)
        with self.assertRaises(ValueError):calculate('X/0',1)
        with self.assertRaises(ValueError):affine('X*X')
    def test_float_edit(self):
        d=Document(struct.pack('<ff',1.25,-2));m=spec(dict(rows=1,cols=2,bits=32,data_type='float'),d);change_cells(d,m,{0:3.5});self.assertEqual(struct.unpack('<ff',d.data),(3.5,-2));d.undo();self.assertEqual(struct.unpack('<ff',d.data),(1.25,-2))
        before=bytes(d.data)
        with self.assertRaises((OverflowError,ValueError)):change_cells(d,m,{0:3,1:1e100})
        self.assertEqual(bytes(d.data),before)
    def test_inverse_check(self):
        d=self.doc();m=spec(dict(rows=2,cols=2,bits=16,equation='X*X',inverse='X/2'),d)
        with self.assertRaises(ValueError):change_cells(d,m,{0:40000})
        self.assertEqual(bytes(d.data),d.original)
    def test_restore_uses_exact_original_bytes(self):
        d=Document(struct.pack('<hh',-2,3));m=spec(dict(rows=1,cols=2,bits=16,signed=True,equation='X*X',inverse='X**0.5'),d);d.edit_bytes(0,struct.pack('<h',8));restore_raw_cells(d,m,[0]);self.assertEqual(d.data,d.original)
    def test_patch_apply_one_undo(self):
        d=self.doc();modified=bytearray(d.data);modified[0]=99;modified[-1]=7;p=make_patch(d.data,modified);apply_patch(d,p);self.assertEqual(d.data,modified);d.undo();self.assertEqual(d.data,d.original)
    def test_patch_wrong_hash_atomic(self):
        d=self.doc();modified=bytearray(d.data);modified[0]=99;p=make_patch(d.data,modified);p['target_sha256']='wrong'
        with self.assertRaises(ValueError):apply_patch(d,p)
        self.assertEqual(d.data,d.original);self.assertFalse(d.undo_stack)
        p['base_sha256']='wrong'
        with self.assertRaises(ValueError):apply_patch(d,p)
    def test_patch_overlap_rejected(self):
        d=self.doc();p=make_patch(d.data,b'\x00'*8);p['runs']=[dict(address=0,before=d.data[:2].hex(),after='0000'),dict(address=1,before=d.data[1:3].hex(),after='0000')]
        with self.assertRaises(ValueError):apply_patch(d,p)
        self.assertEqual(d.data,d.original)
if __name__=='__main__':unittest.main()
