"""원본 함수의 반환값과 지역변수를 읽기만 해 최초 음고 오차를 추적한다."""
import contextlib, dataclasses, io, json, sys
from pathlib import Path
from unittest.mock import patch
root=Path.cwd();sys.path.insert(0,str(root))
import main as CLI
work=root/'output/phase-pitch-trace-20261006'; records=[]
def target(n):
    return getattr(n,'staff_index',None) in (0,1) and 400<=getattr(n,'x',0)<=415

def trace(frame,event,arg):
    fn=frame.f_code.co_filename.replace(chr(92),'/').rsplit('/',1)[-1]; name=frame.f_code.co_name
    if fn not in ('notehead_detect.py','pitch_calculator.py') or name not in ('_refine_y','_detect_noteheads_in_band','detect_noteheads','calculate_pitch'): return None
    if event!='return': return trace
    if fn=='notehead_detect.py' and name=='_refine_y':
        l=frame.f_locals; outer=frame.f_back.f_locals
        if outer['staff'].index in (0,1) and 400<=l['x']<=415:
            keep=('x','y_band','y_lo','y_hi','x0','x1','y0','y1')
            rec=dict(stage='_refine_y',staff=outer['staff'].index,band_top=outer['top'],return_y_band=float(arg),inputs={k:float(l[k]) for k in keep})
            rec['row_ink_counts']=l['rows'].tolist();rec['dense']=l['dense'].tolist()
            rec['opened_bbox']=[int(outer[k]) for k in ('x','y','w','h','area')]
            rec['opening_centroid']=outer['cents'][outer['i']].tolist()
            records.append(rec)
    elif fn=='notehead_detect.py' and name in ('_detect_noteheads_in_band','detect_noteheads') and arg is not None:
        notes=[dataclasses.asdict(n) for n in arg if target(n)]
        if notes: records.append(dict(stage=name,notes=notes))
    elif fn=='pitch_calculator.py' and name=='calculate_pitch' and target(frame.f_locals['notehead']):
        l=frame.f_locals
        records.append(dict(stage='calculate_pitch',head=dataclasses.asdict(l['notehead']),bottom=float(l['bottom_line_y']),spacing=float(l['staff'].spacing),raw_steps=float(l['raw_steps']),step=int(l['step']),clef=l['clef'],note=dataclasses.asdict(arg)))
    return trace
for case,inp in [('original',root/'test_scores/verovio/beethoven_op18no1_bravura_p1.png'),('x0.5',root/'output/header-symbols/phase-0.5-0.png')]:
    records=[];out=work/case;out.mkdir(exist_ok=True);log=io.StringIO()
    argv=['main.py',str(inp),'--no-debug','--output-dir',str(out)]
    try:
        sys.settrace(trace)
        with patch.object(sys,'argv',argv),contextlib.redirect_stdout(log): CLI.run_page(CLI.parse_args(),str(inp),0,str(out))
    finally: sys.settrace(None)
    (out/'source.log').write_text(log.getvalue(),encoding='utf-8')
    (out/'trace.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(case,json.dumps(records,ensure_ascii=False),flush=True)
