"""제품을 바꾸지 않고 기존 보정 창에서 성분별 closing 대응값을 잰다."""
import json,sys,math
from pathlib import Path
import cv2,numpy as np
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
work=ROOT/'output/dynamic-join-fix-20261006';records=[];counts={}
def trace(frame,event,arg):
 if frame.f_code.co_name!='_refine_y' or not frame.f_code.co_filename.endswith('notehead_detect.py'):return None
 if event!='return':return trace
 l=frame.f_locals;o=frame.f_back.f_locals
 x,y,w,h=[int(o[k]) for k in ('x','y','w','h')];i=o['i']
 ids=np.unique(o['band_lab'][y:y+h,x:x+w][(o['_labels'][y:y+h,x:x+w]==i)&(o['band'][y:y+h,x:x+w]>0)])
 ids=ids[ids>0];counts['refine']=counts.get('refine',0)+1
 if len(ids)<2:return trace
 counts['multiple']=counts.get('multiple',0)+1
 py=o['vk'].shape[0]+o['ek'].shape[0];px=o['ek'].shape[1]
 xa=max(0,x-px);xb=min(o['band'].shape[1],x+w+px);ya=max(0,y-py);yb=min(o['band'].shape[0],y+h+py)
 labels=o['band_lab'][ya:yb,xa:xb];blob=o['_labels'][y:y+h,x:x+w]==i;supported=[]
 for component in ids:
  isolated=cv2.morphologyEx(np.uint8(labels==component)*255,cv2.MORPH_CLOSE,o['vk'])
  seeds=cv2.erode(isolated,o['ek'])
  if np.any((seeds[y-ya:y-ya+h,x-xa:x-xa+w]>0)&blob):supported.append((int(component),isolated))
 if len(supported)!=1:return trace
 component,isolated=supported[0]
 yy0=max(0,l['y0']);yy1=max(0,l['y1']);xx0=max(0,l['x0']);xx1=max(0,l['x1'])
 win=isolated[yy0-ya:yy1-ya,xx0-xa:xx1-xa];rows=(win>0).sum(axis=1)
 if rows.size==0 or rows.max()==0:return trace
 dense=np.where(rows>rows.max()*.55)[0]
 alt=float(yy0+(dense[0]+dense[-1])/2)
 if abs(alt-float(arg))>1e-8:
  rec=dict(case=current,staff=o['staff'].index,spacing=o['spacing'],x=l['x'],y_before=float(arg+o['top']),y_after=alt+o['top'],bbox=[x,y+o['top'],w,h],components=ids.tolist(),supported=component,original_bboxes=[o['band_stats'][j].tolist() for j in ids])
  records.append(rec)
 return trace
jobs=json.loads((ROOT/'output/beta-recheck-20261006/inputs.json').read_text(encoding='utf-8'))
jobs.append(dict(name='phase-x0.5',path=str(ROOT/'output/header-symbols/phase-0.5-0.png'),page=0))
for job in jobs:
 current=job['name'];result=preprocess(job['path'],pdf_page=job['page']);contexts=analyze_staves(result)
 start=len(records)
 try:sys.settrace(trace);detect_noteheads(result,contexts=contexts)
 finally:sys.settrace(None)
 (work/'component-probe.json').write_text(json.dumps(dict(counts=counts,changes=records),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(current,'potential_y_changes',len(records)-start,flush=True)
print(json.dumps(counts),flush=True)
