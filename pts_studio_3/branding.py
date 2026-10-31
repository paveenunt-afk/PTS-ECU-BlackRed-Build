"""PTS black/red application and action icons, generated from vector primitives."""
from pathlib import Path
import math
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent/'assets'
FONT=Path(__file__).resolve().parent/'assets'/'brand_font.ttf'

def logo(size=256):
    s=4;im=Image.new('RGBA',(size*s,size*s),(0,0,0,0));d=ImageDraw.Draw(im);n=size*s
    d.rounded_rectangle((8*s,8*s,n-8*s,n-8*s),radius=42*s,fill='#0b0b10',outline='#ef233c',width=6*s)
    d.polygon([(18*s,190*s),(238*s,160*s),(238*s,201*s),(18*s,230*s)],fill='#cb102b') if size==256 else None
    # Coordinates scale from the same 256-unit vector canvas.
    k=n/256
    d.polygon([(18*k,190*k),(238*k,160*k),(238*k,201*k),(18*k,230*k)],fill='#cb102b')
    import os
    winfont=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'arialbd.ttf'
    path=str(FONT) if FONT.exists() else str(winfont) if winfont.exists() else 'DejaVuSans-Bold.ttf'
    font=ImageFont.truetype(path,round(82*k));box=d.textbbox((0,0),'PTS',font=font);w=box[2]-box[0];d.text(((n-w)/2,83*k-box[1]),'PTS',font=font,fill='#ffffff',stroke_width=max(1,round(k)),stroke_fill='#ffffff')
    d.line([(30*k,64*k),(159*k,47*k),(226*k,64*k)],fill='#ef233c',width=max(2,round(5*k)))
    return im.resize((size,size),Image.Resampling.LANCZOS)

def action(name,size=24):
    k=4;im=Image.new('RGBA',(size*k,size*k),(0,0,0,0));d=ImageDraw.Draw(im);red='#ff4058';white='#f1f3f8';scale=size*k/24
    def line(points,fill=red,width=2):d.line([(x*scale,y*scale) for x,y in points],fill=fill,width=max(1,round(width*scale)),joint='curve')
    def rect(box,fill=None,outline=red,width=2):d.rectangle(tuple(v*scale for v in box),fill=fill,outline=outline,width=max(1,round(width*scale)))
    if name=='open':line([(2,7),(2,20),(21,20),(23,9),(9,9),(7,5),(2,5),(2,7)]);line([(3,11),(21,11)],white,1)
    elif name=='save':rect((3,2,21,22));rect((7,2,17,10),outline=white);rect((7,15,17,22),outline=white)
    elif name=='export':rect((3,11,21,22));line([(12,16),(12,2),(7,7)],white);line([(12,2),(17,7)],white)
    elif name in ('undo','redo'):
        points=[(4,8),(13,8),(19,11),(20,16),(17,20)]
        if name=='redo':points=[(24-x,y) for x,y in points]
        line(points,white);arrow=[(8,3),(3,8),(8,13)]
        if name=='redo':arrow=[(24-x,y) for x,y in arrow]
        line(arrow)
    elif name=='graph':
        line([(3,20),(3,3)],white);line([(3,20),(22,20)],white);line([(5,17),(9,12),(13,15),(18,6),(22,8)])
    elif name=='fullscreen':
        for p in [[(2,9),(2,2),(9,2)],[(15,2),(22,2),(22,9)],[(22,15),(22,22),(15,22)],[(9,22),(2,22),(2,15)]]:line(p)
    elif name=='copy':rect((3,3,15,17),outline=white);rect((9,8,21,22))
    elif name=='paste':rect((4,4,20,22));rect((8,2,16,6),fill='#0c1018',outline=white);line([(8,12),(16,12)],white);line([(8,17),(16,17)],white)
    elif name=='percent':
        line([(5,21),(19,3)],white);d.ellipse((3*scale,3*scale,9*scale,9*scale),outline=red,width=max(1,round(2*scale)));d.ellipse((15*scale,15*scale,21*scale,21*scale),outline=red,width=max(1,round(2*scale)))
    elif name=='add':line([(12,4),(12,20)],white);line([(4,12),(20,12)])
    elif name=='edit':line([(4,20),(6,14),(17,3),(21,7),(10,18),(4,20)],white);line([(14,6),(18,10)])
    elif name=='smooth':line([(2,18),(5,18),(9,6),(13,6),(17,18),(22,18)],white);line([(3,13),(21,13)],red,1)
    elif name=='down':line([(12,3),(12,21),(6,15)],white);line([(12,21),(18,15)])
    elif name=='right':line([(3,12),(21,12),(15,6)],white);line([(21,12),(15,18)])
    else:
        rect((3,3,21,21));line([(3,9),(21,9)],white,1);line([(3,15),(21,15)],white,1);line([(9,3),(9,21)],white,1);line([(15,3),(15,21)],white,1)
    return im.resize((size,size),Image.Resampling.LANCZOS)

def main():
    ROOT.mkdir(exist_ok=True)
    logo(256).save(ROOT/'pts.png');logo(256).save(ROOT/'pts.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    for name in ('open','save','export','undo','redo','graph','fullscreen','copy','paste','percent','add','edit','smooth','down','right','table'):
        action(name).save(ROOT/(name+'.png'))
if __name__=='__main__':main()
