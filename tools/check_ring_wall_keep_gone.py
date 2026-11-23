# -*- coding: utf-8 -*-
"""야간 [3] 링 벽 예외 제품판에서 사라진 라벨 분류(nograce ↔ rwkeep) — 오삭제 확인용. 제품 코드 무변경."""
import json,sys
sys.path.insert(0,'.'); sys.path.insert(0,'tools')
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
V = sys.argv[1] if len(sys.argv) > 1 else "rwkeep"
BASE = sys.argv[2] if len(sys.argv) > 2 else "nograce"
def one(job):
    import numpy as np, measure_chord_template as T
    from modules.preprocess import preprocess
    st,name,path,pg=job
    if st=='aoharu' or name=='organ2': return Counter()
    A=json.load(open(f'debug/sim_lp/{BASE}/{name}.json',encoding='utf-8'))['labels']; B=json.load(open(f'debug/sim_lp/{V}/{name}.json',encoding='utf-8'))['labels']
    key=lambda l:(l['staff'],l['x'],l['y'],l['text'],l['pitch'])
    kb={key(l) for l in B}; gone=[l for l in A if key(l) not in kb]
    c=Counter()
    if not gone: return c
    res=preprocess(path,pdf_page=pg) if path.endswith('.pdf') else preprocess(path); heads=T._truth(st,name,path,pg,res); sp=float(np.median([s.spacing for s in res.staves]))
    for l in gone:
        h=[q for q in heads if abs(q[0]-l['x'])<=.7*sp and abs(q[1]-l['y'])<=.5*sp]
        same=[m for m in B if (m['staff'],m['x'],m['y'])==(l['staff'],l['x'],l['y'])]
        if same: c['같은 자리 라벨 바뀜(표기·음고)']+=1
        elif not h: c['유령 사라짐']+=1
        elif any(abs(m['x']-h[0][0])<=.7*sp and abs(m['y']-h[0][1])<=.5*sp for m in B): c['진짜 머리 · 다른 라벨 남음']+=1
        else: c['오삭제']+=1; print('오삭제',name,l['x'],l['y'],l['text'],flush=True)
    return c
if __name__=='__main__':
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex: res=list(ex.map(one,S.pages()))
    t=Counter()
    for c in res: t.update(c)
    print(dict(t))
