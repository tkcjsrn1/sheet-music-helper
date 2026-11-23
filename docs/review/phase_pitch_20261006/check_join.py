import json
from pathlib import Path
import cv2,numpy as np
w=Path('output/phase-pitch-trace-20261006');rows=[]
for case in ('original','x0.5'):
    data=np.load(w/case/'roi.npz')
    rec={'case':case,'crop_xyxy':[385,220,435,275],'head_xy':[406,239],'p_xy':[408,256]}
    for stage in ('no_staff','patched','opened'):
        _,labels=cv2.connectedComponents(data[stage],connectivity=8)
        h=int(labels[239-220,406-385]);p=int(labels[256-220,408-385])
        assert h>0 and p>0
        rec[stage]={'head_component':h,'p_component':p,'joined':h==p}
    rows.append(rec)
assert all(not r['no_staff']['joined'] and r['patched']['joined'] and r['opened']['joined'] for r in rows)
Path('docs/review/phase_pitch_20261006/component-join.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))
