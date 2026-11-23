# -*- coding: utf-8 -*-
"""[4] PDF · 보지 않은 악보 「확실 유령」 중 꾸밈음(작은 머리, 정답 목록 `truth_at`이 빼는 크기) 라벨 수. 입력 debug/certain_errors.json. 제품 코드 무변경."""
import json,sys
sys.path.insert(0,'.'); sys.path.insert(0,'tools')
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
def one(job):
    name,rows=job
    import check_accidental_fix as C, measure_a17_ghost6 as G, measure_omission_rate as M
    from measure_normalize_sp import truth_at
    P={n:(p,pg) for n,p,pg in C.PAGES}; P.update({n:(p,pg) for n,p,pg in G.UNSEEN})
    p,pg=P[name]; g=[q for q in M.pdf_glyphs(p,pg,('noteheads.',))]; t=truth_at(p,pg,1.0)[0]
    big=max(q['size'] for q in g) if g else 0
    out=[]
    for r in rows:
        near=[q for q in g if abs(q['cx']-r['x'])<=12 and abs(q['cy']-r['y'])<=10]
        if not near: out.append('머리 글리프 없음'); continue
        q=min(near,key=lambda q:abs(q['cx']-r['x'])+abs(q['cy']-r['y']))
        intruth=any(abs(h['cx']-q['cx'])<1 and abs(h['cy']-q['cy'])<1 for h in t)
        out.append(('정답 목록에 있음' if intruth else '정답 목록에 없음')+(' · 작은 머리(꾸밈음)' if q['size']<0.8*big else ' · 보통 크기'))
    return out
if __name__=='__main__':
    R=json.load(open('debug/certain_errors.json',encoding='utf-8'))
    by={}
    for r in R:
        if r['conf']=='certain' and r['err']=='유령' and r['set'] in ('pdf','unseen'): by.setdefault(r['page'],[]).append(r)
    with ProcessPoolExecutor(3) as ex: res=[x for p in ex.map(one,list(by.items())) for x in p]
    print(len(res),Counter(res))
