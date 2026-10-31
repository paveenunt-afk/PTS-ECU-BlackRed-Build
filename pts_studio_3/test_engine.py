import base64
import json
import tempfile
import unittest
import zlib
from pathlib import Path
from core import Document
from engine import spec,display_values,change_cells,interpolate,smooth,save_project,load_project,candidate_regions

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.doc=Document(b''.join(i.to_bytes(2,'little') for i in range(16)))
        self.m=spec(dict(address=0,rows=4,cols=4,bits=16,factor=.5,offset=-2),self.doc)
    def test_scaled_edit_is_undoable(self):
        before=bytes(self.doc.data);change_cells(self.doc,self.m,{0:8,3:12});self.assertEqual(display_values(self.doc,self.m)[0],8);self.assertEqual(display_values(self.doc,self.m)[3],12)
        self.doc.undo();self.assertEqual(bytes(self.doc.data),before);self.doc.redo();self.assertEqual(display_values(self.doc,self.m)[0],8)
    def test_bulk_edit_atomic(self):
        before=bytes(self.doc.data)
        with self.assertRaises(OverflowError):change_cells(self.doc,self.m,{0:12,1:999999})
        self.assertEqual(bytes(self.doc.data),before);self.assertFalse(self.doc.undo_stack)
        with self.assertRaises(ValueError):change_cells(self.doc,self.m,{16:3})
        self.assertEqual(bytes(self.doc.data),before)
    def test_bad_scaling_and_axis(self):
        for value in (0,float('nan'),float('inf')):
            with self.assertRaises(ValueError):spec(dict(self.m,factor=value),self.doc)
        with self.assertRaises(ValueError):spec(dict(self.m,x_axis=[1,2]),self.doc)
        with self.assertRaises(ValueError):spec(dict(self.m,signed='false'),self.doc)
        with self.assertRaises(ValueError):spec(dict(self.m,address=-2),self.doc)
    def test_interpolation(self):
        vals=[0,99,99,12,8,9,10,11]
        self.assertEqual(interpolate(vals,2,4,[0,1,2,3],'x'),{0:0,1:4,2:8,3:12})
        self.assertEqual(interpolate([0,5,88,6,10,7],3,2,[0,2,4],'y'),{0:0,2:5,4:10})
        with self.assertRaises(ValueError):interpolate(vals,2,4,[0,1],'x')
    def test_smoothing_does_not_mutate_other_cells(self):
        vals=[0,0,0,0,100,0,0,0,0];self.assertEqual(smooth(vals,3,3,[4]),{4:50});self.assertEqual(vals[4],100)
    def test_project_roundtrip_and_version(self):
        change_cells(self.doc,self.m,{0:3});versions=[dict(name='test',data=base64.b64encode(self.doc.data).decode())]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.pts2';save_project(p,self.doc,[self.m],versions);d,m,v=load_project(p);self.assertEqual(d.data,self.doc.data);self.assertEqual(d.original,self.doc.original);self.assertEqual(m,[self.m]);self.assertEqual(v,versions)
    def test_bad_project_atomic_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.pts2';p.write_bytes(zlib.compress(json.dumps(dict(format='PTS_STUDIO_2',original='AA==',modified='AAAA',maps=[])).encode()))
            with self.assertRaises(ValueError):load_project(p)
    def test_signed_big_endian(self):
        d=Document(b'\xff\xfe\x00\x01');m=spec(dict(address=0,rows=1,cols=2,bits=16,signed=True,endian='big'),d);self.assertEqual(display_values(d,m),[-2,1]);change_cells(d,m,{0:-20});self.assertEqual(d.data[:2],b'\xff\xec')
    def test_candidate_constant_ignored(self):self.assertEqual(candidate_regions(Document(bytes(1024))),[])

if __name__=='__main__':unittest.main()
