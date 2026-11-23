# -*- coding: utf-8 -*-
"""바흐 x 평행이동의 조표와 적용된 음높이·최종 계이름을 기록한다. 제품 무변경."""
import json
from pathlib import Path
import sys
import tempfile
import hashlib
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.verify import drop_beam_ghosts,drop_offstaff_ghosts
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals,remove_accidental_ghosts
from modules.note_namer import to_solfege,resolve_tonic
SOURCE=ROOT/'test_scores/bach_minuet_Am.pdf'
EXPECTED_SHA='86435e170268a04201966492e120371348abbc7d77712221e362b91d97832eeb'

def snapshot(res):
    ctx=analyze_staves(res);heads=detect_noteheads(res,contexts=ctx)
    kept,_=drop_beam_ghosts(res,heads);kept,_=drop_offstaff_ghosts(res,kept)
    notes=calculate_pitches(kept,res.staves,clef={i:c.clef for i,c in ctx.items()})
    acc=annotate_accidentals(res,ctx,notes);notes,acc=remove_accidental_ghosts(notes,acc,res.staves)
    rows=[]
    for n,a in zip(notes,acc):
        c=ctx[n.staff_index]
        alter={'#':1,'b':-1,'natural':0}.get(a,1 if c.key_symbol=='♯' and n.note_name in c.key_letters else -1 if c.key_symbol=='♭' and n.note_name in c.key_letters else 0)
        rows.append(dict(x=n.x,y=n.y,staff=n.staff_index,note_name=n.note_name,octave=n.octave,
            accidental=a,applied_alteration=alter,
            midi=12*(n.octave+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[n.note_name]+alter,
            solfege=to_solfege(n,c.key_letters,c.key_symbol,a),
            movable=to_solfege(n,c.key_letters,c.key_symbol,a,'solfege-movable',tonic=resolve_tonic(c.key_symbol,c.key_count))))
    return dict(staves=len(res.staves),keysigs={i:dict(symbol=c.key_symbol,count=c.key_count,letters=list(c.key_letters),header_end=c.header_end) for i,c in ctx.items()},
        notes=rows,unmarked_B_flat=[r for r in rows if r['note_name']=='B' and not r['accidental'] and r['applied_alteration']==-1])

def measure():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=EXPECTED_SHA:raise ValueError('바흐 원본 해시 불일치')
    base=preprocess(str(SOURCE),pdf_dpi=300)
    out={'original':snapshot(base)}
    with tempfile.TemporaryDirectory(prefix='keysig-shift-') as tmp:
        for dx in [0,.25,.5,.75,1]:
            bgr=cv2.warpAffine(base.original_bgr,np.float32([[1,0,dx],[0,1,0]]),(base.gray.shape[1],base.gray.shape[0]),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
            p=Path(tmp)/'shift.png';ok,buf=cv2.imencode('.png',bgr)
            if not ok:raise ValueError('PNG 인코딩 실패')
            buf.tofile(p)
            out[str(dx)]=snapshot(preprocess(str(p)))
    return dict(source_sha256=EXPECTED_SHA,transform='warpAffine INTER_LINEAR, x만 이동, 흰 경계, 0도 호출 생략 안 함',
                module_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'modules').glob('*.py')},runs=out)

if __name__=='__main__':
    r=measure();p=ROOT/'output/keysig-subpixel/measurement.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for phase,run in r['runs'].items():print(phase,sorted(set((c['symbol'],c['count']) for c in run['keysigs'].values())),'조표 때문에 낮아진 B',len(run['unmarked_B_flat']))
