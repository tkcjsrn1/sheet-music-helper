# -*- coding: utf-8 -*-
"""(b) 링 벽 필터가 지운 꽉 찬 후보의 중심 ±0.2sp 행 가로 잉크 폭(sp) — 진짜 머리 vs 링 벽 조각. 입력 debug/ring_wall.json(measure_ring_wall.py). 제품 코드 무변경."""
import json,sys,os,numpy as np
sys.path.insert(0,'.'); sys.path.insert(0,'tools')
from concurrent.futures import ProcessPoolExecutor
def one(job):
    (st,page),rs=job
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    import check_accidental_fix as C
    res=preprocess(f'test_scores/verovio/{page}.png') if st=='verovio' else preprocess(dict((n,(p,g)) for n,p,g in C.PAGES)[page][0],pdf_page=dict((n,(p,g)) for n,p,g in C.PAGES)[page][1])
    ns=remove_staff_lines(res.binary,res.staves)>0; out=[]
    for r in rs:
        x,y=int(r['x']),int(r['y']); sp=r['sp']; best=0
        for yy in range(int(y-0.2*sp),int(y+0.2*sp)+1):   # 중심 ±0.2sp 행의 가로 잉크 연속 폭 최대
            if not ns[yy,x]: continue
            a=x
            while a>0 and ns[yy,a-1]: a-=1
            b=x
            while b<ns.shape[1]-1 and ns[yy,b+1]: b+=1
            best=max(best,b-a+1)
        out.append((r['what'],round(best/sp,2)))
    return out
if __name__=='__main__':
    R=json.load(open('debug/ring_wall.json',encoding='utf-8'))
    from collections import defaultdict; by=defaultdict(list)
    for r in R: by[(r['set'],r['page'])].append(r)
    with ProcessPoolExecutor(3) as ex: res=[x for p in ex.map(one,by.items()) for x in p]
    for w in sorted({a for a,_ in res}):
        v=np.array([b for a,b in res if a==w]); print(w,len(v),'가로 잉크 폭 sp 최소/5/50/95/최대',np.percentile(v,[0,5,50,95,100]).round(2))
