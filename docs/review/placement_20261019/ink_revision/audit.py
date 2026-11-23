"""고정12쪽 이동 잉크와 실제 출력의 원본 기호 가림을 대조한다. 원본은 로컬 보존본을 사용한다."""
import gzip
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
RECORD=Path(__file__).resolve().parent
LOCAL=ROOT/'output/placement-20261019/ink-revision'
previous=json.loads(gzip.decompress((RECORD.parent/'measurements.json.gz').read_bytes()))
before={r['case']:r for r in previous['baseline']}
rejected={r['case']:r for r in previous['normalise-final']}
current=json.loads((LOCAL/'candidate/results.json').read_text(encoding='utf-8'))
strict={r['case']:r for r in json.loads((ROOT/'output/strict-double-connection/result.json').read_text(encoding='utf-8'))}
symbols=json.loads((RECORD/'symbols.json').read_text(encoding='utf-8'))

def read_image(path):
    return cv2.imdecode(np.fromfile(path,np.uint8),cv2.IMREAD_COLOR)

def count(mask,p,margin=0):
    x0,y0,x1,y1=(int(p['x']-margin),int(p['y']-margin),int(p['x']+p['w']+margin),int(p['y']+p['h']+margin))
    return int(mask[max(0,y0):max(0,y1),max(0,x0):max(0,x1)].sum())

report=[]
for row in current:
    name=row['case'];old=before[name];doc=strict[name]['after']
    assert row['json_sha256']==old['json_sha256'] and row['labels']==old['labels']
    source=read_image(strict[name]['input']);base=read_image(ROOT/old['png']);after=read_image(ROOT/row['png'])
    assert source.shape==base.shape==after.shape
    binary=cv2.cvtColor(source,cv2.COLOR_BGR2GRAY)<128
    protected=np.any(source!=255,axis=2)
    for staff in doc['staves']:
        for y in staff['line_ys']:
            binary[max(0,round(y)-1):round(y)+2,:]=False
            protected[max(0,round(y)-1):round(y)+2,:]=False
    oldps={p['index']:p for p in old['placed']};newps={p['index']:p for p in row['placed']}
    assert oldps.keys()==newps.keys()
    changed=[];body_increase=[];decoration_increase=[]
    spacing={s['id']:s['spacing'] for s in doc['staves']}
    for i,p in newps.items():
        o=oldps[i];label=row['labels'][i];px=max(16,round(spacing[label['staff']]*1.1));m=max(2,round(px*.11))+2+(2 if label['confidence']=='check' else 0)
        assert count(binary,p)==p['ink_pixels'] and count(binary,o)==o['ink_pixels']
        if (p['x'],p['y'])!=(o['x'],o['y']):changed.append(i)
        if count(binary,p)>count(binary,o):body_increase.append(i)
        if count(binary,p,m)>count(binary,o,m):decoration_increase.append(i)
        assert p['gap']<=o['gap']
    old_error=np.abs(base.astype(np.int16)-source.astype(np.int16))
    error=np.abs(after.astype(np.int16)-source.astype(np.int16))
    worse=protected & np.any(error>old_error,axis=2)
    newly_hidden=protected & ~np.any(old_error,axis=2) & np.any(error,axis=2)
    entry=dict(case=name,labels=len(newps),changed=len(changed),changed_indices=changed,
        source_json_sha256=row['json_sha256'],source_image_sha256=hashlib.sha256(Path(strict[name]['input']).read_bytes()).hexdigest(),
        increased_source_ink_labels=len(body_increase),body_increase_indices=body_increase,
        increased_ink_with_decoration_labels=len(decoration_increase),decoration_increase_indices=decoration_increase,
        newly_hidden_source_pixels=int(newly_hidden.sum()),worsened_nonstaff_source_pixels=int(worse.sum()),
        newly_hidden_symbols=0 if not worse.any() else None,
        symbol_count_basis='비오선 원본 비흰 화소 악화0으로 신규 가림0 확인. 글리프를 자동 인식/계수한 것은 아님.',
        before_metrics=old['metrics'],after_metrics=row['metrics'])
    if name==symbols['case']:
        bad=read_image(ROOT/rejected[name]['png'])
        bad_error=np.abs(bad.astype(np.int16)-source.astype(np.int16))
        rois=[]
        for symbol in symbols['symbols']:
            x0,y0,x1,y1=symbol['rect'];mask=protected[y0:y1,x0:x1]
            bad_pixels=int(np.count_nonzero(mask & np.any(bad_error[y0:y1,x0:x1]>old_error[y0:y1,x0:x1],axis=2)))
            new_pixels=int(worse[y0:y1,x0:x1].sum())
            rois.append(dict(**symbol,rejected_v1_worsened_pixels=bad_pixels,revised_worsened_pixels=new_pixels))
        entry['symbols']=rois
        entry['audited_symbol_regions']=len(rois)
        entry['newly_hidden_audited_symbols']=sum(r['revised_worsened_pixels']>0 for r in rois)
    for key in ('head_hits','box_hits','bar_crossings','order_inversions'):
        assert not set(map(tuple,row['metrics'][key]))-set(map(tuple,old['metrics'][key])),(name,key)
    report.append(entry)
    (LOCAL/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(name,'moved',len(changed),'ink increased',len(body_increase),'stroke/check increased',len(decoration_increase),'new hidden symbols',entry['newly_hidden_symbols'],'worsened pixels',entry['worsened_nonstaff_source_pixels'],flush=True)
    assert not (body_increase or decoration_increase or worse.any() or newly_hidden.any()),name
assert len(report)==12 and sum(r['labels'] for r in report)==4721
