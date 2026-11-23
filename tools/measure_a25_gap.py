# -*- coding: utf-8 -*-
"""A-25 사전 측정 — 마디선 후보와 가장 가까운 음표 사이 거리 · 흰 틈. 제품 코드 무변경.

후보 = `debug/barline_stem/candidates.json`(제품 `_find_barlines` 출력 + 정답 라벨, `measure_barline_stem.py collect`).
음표 x = 정밀 판정 제품 라벨(`debug/a17_cand1_impl` · `debug/vrv_impl`). PDF 정답 보정: x < 300 「기둥」은 LilyPond 첫머리선(0.23pt)으로 마디선 처리 —
**이 근사는 em1 · em4 첫 음표 기둥까지 마디선으로 바꿨다(A25_BARLINE.md §3).** Aoharu는 정답 마디선이 없어 큰보표 관통 후보를 마디선 근사로 쓴다.

    python tools/measure_a25_gap.py      → debug/barline_stem/gap.json (거리 d ≤ 1.2sp 후보의 흰 틈)
"""
import json,sys,numpy as np
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,'tools'); sys.path.insert(0,'.')
def labels(st,page):
    p=f'debug/vrv_impl/base/{page}.json' if st=='verovio' else f'debug/a17_cand1_impl/base_pdf20/{page}.json'
    return json.load(open(p,encoding='utf-8'))['labels']
def one(args):
    import measure_barline_stem as B
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    st,page,cands=args
    P={(p[0],p[1]):p for p in B.pages()}[(st,page)]
    res=preprocess(P[2],pdf_page=P[3]) if P[2].endswith('.pdf') else preprocess(P[2])
    ns=remove_staff_lines(res.binary,res.staves)>0
    L=labels(st,page); out=[]
    for r in cands:
        sp=r['sp']; mine=[l for l in L if l['staff']==r['staff']]
        l=min(mine,key=lambda l:abs(l['x']-r['x']))
        a,b=sorted((int(r['x']),int(l['x'])))
        y0,y1=int(l['y']-0.25*sp),int(l['y']+0.25*sp)+1
        cols=ns[y0:y1,a:b+1].any(axis=0)
        # 막대 열에서 머리 쪽으로 처음 흰 열까지 — 흰 열이 하나라도 있으면 틈
        gap=int((~cols).sum())
        out.append(dict(set=st,page=page,x=r['x'],truth=r['t'],d=r['d'],gap_px=gap,gap_sp=gap/sp))
    return out
if __name__=='__main__':
    C=json.load(open('debug/barline_stem/candidates.json',encoding='utf-8'))
    byp=defaultdict(list); cache={}
    for r in C:
        k=(r['set'],r['page'])
        if k not in cache: cache[k]=labels(*k)
        xs=[l['x'] for l in cache[k] if l['staff']==r['staff']]
        if len(xs)<2 or not (min(xs)<r['x']<max(xs)): continue
        d=min(abs(r['x']-x) for x in xs)/r['sp']
        t=r['truth']
        if r['set']=='pdf' and t=='stem' and r['x']<300: t='barline'
        if r['set']=='aoharu': t='barline' if (r['joins_up'] or r['joins_down']) else 'stem?'
        if t in ('barline','stem','stem?') and d<=1.2:
            byp[k].append(dict(r,t=t,d=d))
    with ProcessPoolExecutor(2) as ex:
        rows=[x for part in ex.map(one,[(k[0],k[1],v) for k,v in byp.items()]) for x in part]
    json.dump(rows,open('debug/barline_stem/gap.json','w',encoding='utf-8'))
    for st in ('pdf','verovio','aoharu'):
        for t in ('barline','stem','stem?'):
            v=[r for r in rows if r['set']==st and r['truth']==t and r['d']<=0.9]
            if v:
                g=np.array([r['gap_sp'] for r in v])
                print(f"{st:8s} {t:7s} (음표 0.9sp 안) n {len(v):4d} 틈 0 {np.sum(g==0):4d} · 틈>0 {np.sum(g>0):4d} | 틈 sp 최소 {g.min():.2f} 중앙 {np.median(g):.2f} 최대 {g.max():.2f}")
