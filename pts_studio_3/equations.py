"""Bounded expression interpreter; never evaluates Python code."""
import ast
import math
from functools import lru_cache

@lru_cache(maxsize=512)
def parse(source):
    if not isinstance(source,str) or len(source)>400:raise ValueError('สูตรยาวเกินกำหนด')
    tree=ast.parse(source.strip().replace('^','**'),mode='eval')
    if len(list(ast.walk(tree)))>100:raise ValueError('สูตรซับซ้อนเกินกำหนด')
    for n in ast.walk(tree):
        if not isinstance(n,(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.UAdd,ast.USub,ast.Constant,ast.Name,ast.Load)):raise ValueError('สูตรรองรับ X ตัวเลข + - * / และยกกำลังคงที่เท่านั้น')
        if isinstance(n,ast.Name) and n.id.upper()!='X':raise ValueError('สูตรใช้ตัวแปร X ได้ตัวเดียว')
        if isinstance(n,ast.Constant) and (type(n.value) not in (int,float) or not math.isfinite(n.value) or abs(n.value)>1e100):raise ValueError('ค่าคงที่ในสูตรไม่ถูกต้อง')
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Pow):
            if not isinstance(n.right,ast.Constant) or type(n.right.value) not in (int,float) or abs(n.right.value)>8:raise ValueError('เลขยกกำลังต้องเป็นค่าคงที่ระหว่าง -8 ถึง 8')
    return tree.body

def calculate(source,x):
    def run(n):
        if isinstance(n,ast.Constant):return float(n.value)
        if isinstance(n,ast.Name):return float(x)
        if isinstance(n,ast.UnaryOp):return -run(n.operand) if isinstance(n.op,ast.USub) else run(n.operand)
        a=run(n.left);b=run(n.right)
        if isinstance(n.op,ast.Add):v=a+b
        elif isinstance(n.op,ast.Sub):v=a-b
        elif isinstance(n.op,ast.Mult):v=a*b
        elif isinstance(n.op,ast.Div):v=a/b
        else:v=a**b
        if not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e100:raise ValueError('ผลสูตรอยู่นอกช่วงที่รองรับ')
        return v
    try:return run(parse(source))
    except (ZeroDivisionError,OverflowError) as exc:raise ValueError('สูตรคำนวณไม่ได้ที่ค่านี้') from exc

def affine(source):
    """Symbolically prove f(X)=aX+b, instead of guessing from sample points."""
    def run(n):
        if isinstance(n,ast.Constant):return (0,float(n.value))
        if isinstance(n,ast.Name):return (1.,0.)
        if isinstance(n,ast.UnaryOp):
            a,b=run(n.operand);return (-a,-b) if isinstance(n.op,ast.USub) else (a,b)
        a,b=run(n.left);c,d=run(n.right)
        if isinstance(n.op,ast.Add):return a+c,b+d
        if isinstance(n.op,ast.Sub):return a-c,b-d
        if isinstance(n.op,ast.Mult):
            if a and c:raise ValueError('สูตรไม่เป็นเชิงเส้น')
            return a*d+b*c,b*d
        if isinstance(n.op,ast.Div):
            if c or not d:raise ValueError('สูตรไม่เป็นเชิงเส้น')
            return a/d,b/d
        if isinstance(n.op,ast.Pow):
            if d==1:return a,b
            if d==0:return 0.,1.
            if a:raise ValueError('สูตรไม่เป็นเชิงเส้น')
            return 0.,b**d
        raise ValueError('สูตรไม่เป็นเชิงเส้น')
    return run(parse(source))
