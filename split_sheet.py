"""Extract the atlas's 56 alpha silhouettes without clipping them at nominal cell boundaries."""
from collections import deque
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw
from roster import CHARACTERS

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'generated/cnk-spritesheet-v1/portraits.png'


def split(source=SOURCE,out=HERE):
    im=Image.open(source).convert('RGBA')
    rgba=np.array(im);alpha=rgba[:,:,3];h,w=alpha.shape
    mask=alpha>=128;labels=np.zeros((h,w),np.int16);parts=[]
    visited=np.zeros((h,w),bool)
    for y in range(h):
        for x in range(w):
            if not mask[y,x] or visited[y,x]:continue
            visited[y,x]=True;queue=deque([(x,y)]);pixels=[]
            while queue:
                xx,yy=queue.popleft();pixels.append((xx,yy))
                for nx,ny in ((xx-1,yy),(xx+1,yy),(xx,yy-1),(xx,yy+1)):
                    if 0<=nx<w and 0<=ny<h and mask[ny,nx] and not visited[ny,nx]:
                        visited[ny,nx]=True;queue.append((nx,ny))
            if len(pixels)>100:
                number=len(parts)+1
                xs,ys=np.array(pixels).T
                labels[ys,xs]=number
                parts.append(dict(label=number,area=len(pixels),cx=float(xs.mean()),cy=float(ys.mean())))
    assert len(parts)==56,len(parts)
    # Extend each silhouette through its existing soft alpha fringe. No source
    # colors are synthesized, and opaque pixels never change owners.
    for _ in range(8):
        before=labels.copy()
        for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
            neighbor=np.roll(before,(dy,dx),(0,1))
            if dy<0:neighbor[-1]=0
            if dy>0:neighbor[0]=0
            if dx<0:neighbor[:,-1]=0
            if dx>0:neighbor[:,0]=0
            grow=(labels==0)&(neighbor>0)&(alpha>0)
            labels[grow]=neighbor[grow]
    (out/'split').mkdir(parents=True,exist_ok=True)
    (out/'art').mkdir(parents=True,exist_ok=True)
    found=set();manifest=[]
    preview=Image.new('RGBA',(8*160,7*160),(35,38,43,255));draw=ImageDraw.Draw(preview)
    for part in parts:
        row=min(6,int(part['cy']*7/h));col=min(7,int(part['cx']*8/w))
        index=row*8+col;name=CHARACTERS[index]
        assert index not in found,('two silhouettes in one cell',name)
        found.add(index)
        ys,xs=np.where(labels==part['label'])
        box=(int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1))
        cut=rgba[box[1]:box[3],box[0]:box[2]].copy()
        ownership=labels[box[1]:box[3],box[0]:box[2]]==part['label']
        cut[~ownership]=0
        head=Image.fromarray(cut)
        head.save(out/'split'/(name+'.png'))
        # Equal visual scale, complete silhouettes, square RGBA game assets.
        scale=116/max(head.size)
        size=tuple(max(1,round(n*scale)) for n in head.size)
        head=head.resize(size,Image.Resampling.NEAREST)
        canvas=Image.new('RGBA',(128,128))
        canvas.alpha_composite(head,((128-size[0])//2,(128-size[1])//2))
        canvas.save(out/'art'/(name+'.png'))
        preview.alpha_composite(canvas,(col*160+16,row*160+4))
        draw.text((col*160+5,row*160+137),name,fill='white')
        manifest.append(dict(character=name,row=row+1,column=col+1,source_bbox=list(box),
                             opaque_pixels=part['area'],source_size=list(Image.fromarray(cut).size)))
    assert found==set(range(56))
    assert np.count_nonzero((alpha>=128)&(labels==0))<100
    preview.save(out/'split-preview.png')
    (out/'split-manifest.json').write_text(json.dumps(sorted(manifest,key=lambda r:(r['row'],r['column'])),indent=2)+'\n')
    print('Extracted 56 complete silhouettes; all 56 canonical filenames mapped once.')
    print('Source opaque pixels preserved:',np.count_nonzero((alpha>=128)&(labels>0)))
    print('Unassigned opaque speck pixels:',np.count_nonzero((alpha>=128)&(labels==0)))
    print('Preview:',out/'split-preview.png')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',nargs='?',type=Path,default=SOURCE)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    split(args.source,args.output or args.source.parent/'extracted')
