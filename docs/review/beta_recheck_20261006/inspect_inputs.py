import json,sys,hashlib
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root),str(root/'tools')]
from measure_sim_ledger_pair import pages
rows=[]
for kind,name,path,page in pages():
    candidates=[root/path,Path('C:/Users/user/Desktop/악보헬퍼')/path,Path('C:/Users/user/Documents/악보헬퍼')/path]
    found=next((p for p in candidates if p.is_file()),None)
    baseline=root/'output/header-symbols/matrix-final/after'/name/'labels.json'
    row=dict(kind=kind,name=name,path=str(found) if found else None,page=page,baseline=str(baseline),baseline_exists=baseline.is_file())
    if found and baseline.is_file():
        d=json.loads(baseline.read_text(encoding='utf-8'));row['baseline_input_equal']=d['source']['sha256']==hashlib.sha256(found.read_bytes()).hexdigest() and d['source']['page']==page
    rows.append(row)
(root/'output/beta-recheck-20261006/inputs.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('대상',len(rows),'원본 없음',[r['name'] for r in rows if not r['path']],'기준 없음',[r['name'] for r in rows if not r['baseline_exists']],'입력 불일치',[r['name'] for r in rows if r.get('baseline_input_equal') is False])
assert len(rows)==49 and all(r['path'] and r['baseline_exists'] and r['baseline_input_equal'] for r in rows)