import unittest
from core import Document, validate_map
class Tests(unittest.TestCase):
    def test_endian_undo_redo(self):
        d=Document(b'\x01\x00\xff\xff'); self.assertEqual(d.values(0,1,2),[1,65535]); self.assertEqual(d.values(0,1,2,signed=True),[1,-1]); self.assertEqual(d.values(0,1,2,endian='big'),[256,65535]); d.edit(0,[300]); self.assertEqual(d.data[:2],b'\x2c\x01'); d.undo(); self.assertEqual(bytes(d.data),d.original); d.redo(); self.assertEqual(d.values(0,1,1),[300])
    def test_atomic_overflow_and_bounds(self):
        d=Document(bytes(4))
        with self.assertRaises(OverflowError):d.edit(0,[2,999999])
        self.assertEqual(bytes(d.data),bytes(4)); self.assertFalse(d.undo_stack)
        with self.assertRaises(ValueError):d.values(3,1,2)
        with self.assertRaises(ValueError):d.edit(-1,[1])
    def test_map_and_compare(self):
        d=Document(bytes(8)); m=validate_map(dict(name='test',address=0,rows=2,cols=2),d); self.assertEqual(m['bits'],16)
        with self.assertRaises(ValueError):validate_map(dict(address=4,rows=2,cols=2),d)
        self.assertEqual(d.differences(bytes(7)),[(7,0,None)])
if __name__=='__main__':unittest.main()
