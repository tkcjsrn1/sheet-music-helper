# -*- coding: utf-8 -*-
"""원본/오선 제거/closing 단계의 막대 연결을 관찰한다. 제품 코드는 바꾸지 않는다."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = args.root.resolve()
sys.path[:0] = [str(root), str(root/'tools')]
from modules import accidental_detect as ad
from modules.preprocess import preprocess
from modules.notehead_detect import remove_staff_lines, detect_noteheads
from modules.clef_keysig import analyze_staves
from modules.pitch_calculator import calculate_pitches
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
from measure_accidental_windows import observe_annotation

# 좌표는 음표 피해 위치가 아니라 잘못된 직접 임시표를 받은 방아쇠 위치다.
targets = {
 ('chopin_nocturne_Bbm.pdf',1): [(548,1426),(601,1426),(710,1436),(834,1456)],
 ('chopin_nocturne_Bbm.pdf',2): [(1303,322)],
 ('chopin_nocturne_Bbm.pdf',6): [(1400,324)],
 ('chopin_nocturne_Db_6-8.pdf',5): [(756,2128),(2176,2118)],
 ('chopin_nocturne_Em.pdf',4): [(1859,458)],
 ('bach_minuet_Am.pdf',1): [],
}
known_controls = {
 ('chopin_nocturne_Bbm.pdf',2): [(1527,2534),(1909,2540),(2230,2534)],
 ('bach_minuet_Am.pdf',1): [(526,1102),(1508,1364),(1312,1874)],
}
# 이번 원본 확대 대조로 확인한 기호. 원시 분류까지 원본과 일치한 창만 대조군이다.
visual_controls = {
 ('chopin_nocturne_Bbm.pdf',1): [(755,712),(2023,712)],
 ('chopin_nocturne_Bbm.pdf',2): [(563,342),(1174,332)],
 ('chopin_nocturne_Bbm.pdf',6): [(568,344),(1201,334)],
 ('chopin_nocturne_Db_6-8.pdf',5): [(774,212),(960,222)],
 ('chopin_nocturne_Em.pdf',4): [(292,203)],
 ('bach_minuet_Am.pdf',1): [(1798,424)],
}

def connection(p, bars):
    _, cc = cv2.connectedComponents((p > 0).astype('uint8'), connectivity=8)
    ids = []
    for x,s,e in bars:
        ids.append(set(int(v) for v in cc[int(s):int(e)+1,int(x)] if v))
    return bool(ids[0] & ids[1])

out=[]; tiles=[]
for (filename,page), bad in targets.items():
    with contextlib.redirect_stdout(io.StringIO()):
        r=preprocess(str(root/'test_scores'/filename),pdf_page=page-1)
        ctx=analyze_staves(r); h=detect_noteheads(r,contexts=ctx)
        h,_=drop_beam_ghosts(r,h); h,_=drop_offstaff_ghosts(r,h)
        notes=calculate_pitches(h,r.staves,clef={i:c.clef for i,c in ctx.items()})
        raw,eff,evidence=observe_annotation(r,ctx,notes)
    ns=remove_staff_lines(r.binary,r.staves)
    ss={s.index:s.spacing for s in r.staves}
    selected_extra=0
    for n,kind in zip(notes,raw):
        if kind not in ('#','natural'): continue
        g=evidence[id(n)]; x0,y0=g['patch_origin']; height,width=g['patch_shape']; sp=ss[n.staff_index]
        # 제품이 실제 사용한 보표 밴드 closing을 그대로 재구성한다.
        staff=next(s for s in r.staves if s.index==n.staff_index)
        top=max(0,int(staff.top-sp*3.5)); bottom=min(ns.shape[0],int(staff.bottom+sp*3.5))
        # 페이지 전체 closing은 보표 밴드 경계와 달라질 수 있으므로 제품 밴드를 그대로 쓴다.
        closed=cv2.morphologyEx(ns[top:bottom],cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(3,int(sp*.4))|1)))
        stages={'binary':r.binary[y0:y0+height,x0:x0+width], 'no_staff':ns[y0:y0+height,x0:x0+width], 'closed':closed[y0-top:y0-top+height,x0:x0+width]}
        cp=stages['closed']; bs=ad._find_thin_bars(cp,sp)
        assert [[x+x0,s+y0,e+y0] for x,s,e in bs] == g['bars']
        pairs=[]
        for a,b in zip(bs,bs[1:]):
            if not sp*.3<=b[0]-a[0]<=sp*.95:continue
            cy=(a[1]+a[2]+b[1]+b[2])/4
            k='natural' if a[1]+sp*.45<b[1] and a[2]+sp*.45<b[2] else '#'
            if k==kind and abs(cy+y0-n.y)<=sp*ad.ACCIDENTAL_Y_TOL_SP:pairs.append((abs(cy+y0-n.y),a,b))
        assert pairs
        _,a,b=min(pairs)
        point=(n.x,n.y)
        group='direct_error' if point in bad else ('known_control' if point in known_controls.get((filename,page),[]) else ('visual_control' if point in visual_controls.get((filename,page),[]) else 'unreviewed'))
        if (filename,page,point)==('chopin_nocturne_Em.pdf',4,(292,222)): group='observed_mismatch'
        row={'source':filename,'page':page,'point':point,'kind':kind,'group':group,'sp':sp,'bars':[[x+x0,s+y0,e+y0] for x,s,e in (a,b)],'stages':{}}
        for name,p in stages.items():
            columns=[]
            for x,s,e in (a,b):
                col=p[s:e+1,int(x)]>0
                columns.append({'ink':int(col.sum()),'span':len(col),'runs':int(np.count_nonzero(np.diff(np.r_[False,col].astype(int))==1))})
            row['stages'][name]={'shared_component':connection(p,(a,b)), 'columns':columns,'glyphs':[[k,cy+y0] for k,cy in ad._find_glyphs(p,sp)]}
        row['added_on_bars']=[int(np.count_nonzero((cp[s:e+1,int(x)]>0)&(stages['no_staff'][s:e+1,int(x)]==0))) for x,s,e in (a,b)]
        out.append(row)
        # 이미 확인된 6개와 오류 9개, 나머지는 각 쪽 앞 2개를 육안 대조용으로 제공한다.
        show=group!='unreviewed' or selected_extra<2
        if show:
            if group=='unreviewed':selected_extra+=1
            tile=Image.new('RGB',(600,230),'white'); d=ImageDraw.Draw(tile)
            d.text((4,3),f'{len(out)-1} {filename} p{page} {point} {group}',fill='black')
            crop=Image.fromarray(r.original_bgr[:,:,::-1]).crop((x0-8,y0-5,x0+width+12,y0+height+5)).resize((140,190))
            tile.paste(crop,(0,30))
            for j,(name,p) in enumerate(stages.items()):
                rgb=np.repeat((255-p)[:,:,None],3,axis=2)
                if name=='closed':rgb[(p>0)&(stages['no_staff']==0)]=[255,0,0]
                tile.paste(Image.fromarray(rgb).resize((120,190)),(150+j*145,30))
                d.text((150+j*145,18),name,fill='black')
            tiles.append(tile)
    print(filename,page,'measured',sum(v['source']==filename and v['page']==page for v in out),flush=True)
assert sum(v['group']=='direct_error' for v in out)==9
assert sum(v['group']=='known_control' for v in out)==6
assert sum(v['group']=='visual_control' for v in out)==10
args.output.mkdir(parents=True,exist_ok=True)
report={'ground_truth':False,'note':'known_control은 기존 육안 확인 6곳, visual_control은 추가 육안 확인 10개 창. observed_mismatch는 샤프 획과 기둥을 natural로 묶은 추가 관찰. unreviewed는 정상 정답이 아님. 두 막대의 연결 여부는 패치 안 8연결 성분 교집합.', 'source_sha256':{f:hashlib.sha256((root/'test_scores'/f).read_bytes()).hexdigest() for f,p in targets}, 'module_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'modules').glob('*.py')},'rows':out}
(args.output/'connections.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for start in range(0,len(tiles),5):
    sheet=Image.new('RGB',(600,230*len(tiles[start:start+5])),'white')
    for i,t in enumerate(tiles[start:start+5]):sheet.paste(t,(0,i*230))
    sheet.save(args.output/f'connections-{start//5+1}.png')
for group in ('direct_error','known_control','visual_control','observed_mismatch','unreviewed'):
    rows=[v for v in out if v['group']==group]
    print(group,len(rows),'shared',[sum(v['stages'][s]['shared_component'] for v in rows) for s in ('binary','no_staff','closed')],flush=True)
