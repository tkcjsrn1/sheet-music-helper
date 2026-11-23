"""실제로 호출된 검출 함수 안의 중간 영상을 읽고 해당 음표 부분만 그린다."""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path.cwd();sys.path.insert(0,str(root))
from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
work=root/'output/phase-pitch-trace-20261006'
rows=[]
for case,path in [('original',root/'test_scores/verovio/beethoven_op18no1_bravura_p1.png'),('x0.5',root/'output/header-symbols/phase-0.5-0.png')]:
    result=preprocess(str(path));contexts=analyze_staves(result);saved={}
    def trace(frame,event,arg):
        if frame.f_code.co_name!='_refine_y' or not frame.f_code.co_filename.replace(chr(92),'/').endswith('modules/notehead_detect.py'): return None
        if event=='return' and not saved and 400<=frame.f_locals['x']<=415 and frame.f_back.f_locals['staff'].index==0:
            outer=frame.f_back.f_locals;xa,xb,ya,yb=385,435,220,275;top=outer['top']
            saved['gray']=result.gray[ya:yb,xa:xb].copy()
            saved['no_staff']=outer['no_staff_img'][ya:yb,xa:xb].copy()
            saved['patched']=outer['patched'][ya-top:yb-top,xa:xb].copy()
            saved['opened']=outer['opened'][ya-top:yb-top,xa:xb].copy()
            saved['component']=(outer['_labels'][ya-top:yb-top,xa:xb]==outer['i']).astype(np.uint8)*255
        return trace
    try:
        sys.settrace(trace);heads=detect_noteheads(result,contexts=contexts)
    finally:sys.settrace(None)
    np.savez_compressed(work/case/'roi.npz',**saved)
    rows.append(saved)
fig,axes=plt.subplots(2,5,figsize=(12,6),sharex=True,sharey=True)
for r,(case,data) in enumerate(zip(('original','x +0.5px'),rows)):
    for c,(kind,arr) in enumerate(data.items()):
        ax=axes[r,c];ax.imshow(arr if kind=='gray' else 255-arr,cmap='gray',vmin=0,vmax=255,extent=(384.5,434.5,274.5,219.5))
        ax.axhline(239.3,color='green',linewidth=.7);ax.axhline(243.5,color='red',linewidth=.7,linestyle='--')
        ax.set_title(case+' / '+kind,fontsize=9)
        if c==0:ax.set_ylabel('y (px)')
        if r==1:ax.set_xlabel('x (px)')
fig.text(.02,.01,'Green: TSV head center y=239.3. Red dashed: F4/E4 rounding boundary y=243.5. Pixel crops from actual detection.',fontsize=9)
fig.tight_layout(rect=(0,.045,1,1));fig.savefig(work/'stages.png',dpi=160);plt.close(fig)
print('실제 검출 안의 원본/오선제거/닫힘/열림/해당성분 부분 자료 저장')
