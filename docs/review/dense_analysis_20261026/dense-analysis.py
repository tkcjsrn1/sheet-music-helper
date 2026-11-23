import gzip,hashlib,json
from pathlib import Path
r=Path('F:/akbo-data/tmp/public-prep-20261026'); src=r/'docs/review/label_lanes_20261019/measurements.json.gz'; a=next(x for x in json.loads(gzip.decompress(src.read_bytes())) if x['case']=='chopin_Db_p1')
box=(350,2470,2470,3070)
def overlaps(a,b): return min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1])
assert overlaps((0,0,2,2),(1,1,3,3)) and not overlaps((0,0,1,1),(1,0,2,1))
def rect(p): return p['x'],p['y'],p['x']+p['w'],p['y']+p['h']
rows=[]
for mode in ('default','lanes'):
 labels=[p for p in a[mode] if overlaps(rect(p),box)]
 pairs=[dict(a=p['index'],b=q['index'],a_text=p['text'],b_text=q['text'],a_rect=rect(p),b_rect=rect(q)) for i,p in enumerate(labels) for q in labels[i+1:] if overlaps(rect(p),rect(q))]
 rows.append(dict(mode=mode,labels_intersecting_crop=len(labels),overlapping_label_rectangle_pairs=len(pairs),involved_label_indices=sorted(set(k for p in pairs for k in (p['a'],p['b']))),pairs=pairs,staffs=sorted(set(p['staff'] for p in labels))))
out=dict(basis='기존 015908d 고정 JSON에서 만든10-20 배치자료 재집계; 새 인식/렌더0',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),crop=box,rows=rows)
d=r/'docs/review/dense_analysis_20261026'; d.mkdir(parents=True,exist_ok=True); (d/'existing-rectangles.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(out,ensure_ascii=False,indent=2))
