import unittest,struct
from core import Document
from xdf_io import parse_xdf,display_text
from native_xdf import MAGIC,_READ_KEY,_stream,read_native_xdf
from engine import display_values,change_cells,refresh_linked_axes

def envelope(xml):
    header=bytearray(264);header[:4]=MAGIC;header[131]=100
    return bytes(header)+_stream(xml.encode('utf-8'),_READ_KEY)

XML='''<XDFFORMAT><XDFHEADER><DEFAULTS datasizeinbits="16" lsbfirst="0"/></XDFHEADER>
<XDFTABLE uniqueid="1"><title>Throttle</title><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0" mmedelementsizebits="16" mmedrowcount="2"/><MATH equation="X/10"/></XDFAXIS></XDFTABLE>
<XDFTABLE uniqueid="2"><title>RPM</title><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="4" mmedelementsizebits="16" mmedrowcount="3"/><MATH equation="X"/></XDFAXIS></XDFTABLE>
<XDFTABLE uniqueid="3"><title>Fuel</title><XDFAXIS id="x"><indexcount>2</indexcount><embedinfo type="3" linkobjid="1"/></XDFAXIS><XDFAXIS id="y"><indexcount>3</indexcount><embedinfo type="3" linkobjid="2"/></XDFAXIS><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="10" mmedelementsizebits="16" mmedrowcount="3" mmedcolcount="2"/><MATH equation="X/1000"/></XDFAXIS></XDFTABLE></XDFFORMAT>'''
class NativeTests(unittest.TestCase):
    def doc(self):return Document(struct.pack('>11H',0,1000,1000,2000,3000,500,600,700,800,900,1000))
    def test_standard_rc4_vector(self):self.assertEqual(_stream(b'Plaintext',b'Key').hex(),'bbf316e8d940af0ad3')
    def test_native_read_and_bin_unchanged(self):
        native=envelope(XML);doc=self.doc();maps,report=parse_xdf(native,doc);self.assertEqual(len(maps),3);self.assertEqual(doc.data,doc.original);self.assertEqual(read_native_xdf(native).decode(),XML);self.assertIn('ไบนารี',report[-1])
    def test_linked_axes_resolve_and_refresh(self):
        d=self.doc();maps,_=parse_xdf(envelope(XML),d);fuel=maps[2];self.assertEqual(fuel['x_axis'],[0,100]);self.assertEqual(fuel['y_axis'],[1000,2000,3000]);change_cells(d,maps[0],{1:200});refresh_linked_axes(d,fuel);self.assertEqual(fuel['x_axis'],[0,200]);d.undo();refresh_linked_axes(d,fuel);self.assertEqual(fuel['x_axis'],[0,100])
    def test_formula_edit_targets_correct_two_bytes(self):
        d=self.doc();maps,_=parse_xdf(envelope(XML),d);change_cells(d,maps[2],{0:1.234});self.assertEqual(d.data[10:12],b'\x04\xd2');self.assertEqual(d.data[:10],d.original[:10]);self.assertEqual(d.data[12:],d.original[12:]);d.undo();self.assertEqual(d.data,d.original)
    def test_open_password_is_not_bypassed(self):
        raw=bytearray(envelope(XML));raw[131]=0
        with self.assertRaises(ValueError):read_native_xdf(raw)
    def test_corrupt_and_truncated_fail(self):
        for raw in (MAGIC+b'\0'*10, MAGIC+b'\0'*127+b'd'+b'\0'*200):
            with self.assertRaises(ValueError):read_native_xdf(raw)
    def test_thai_mojibake_labels_only(self):
        self.assertEqual(display_text('คันเร่ง'.encode('cp874').decode('cp1252')),'คันเร่ง');self.assertEqual(display_text('Café'),'Café');self.assertEqual(display_text('RPM'),'RPM')
if __name__=='__main__':unittest.main()
