import contextlib, io, json, sys
from pathlib import Path
from unittest.mock import patch
import cv2, numpy as np
root=Path.cwd();sys.path.insert(0,str(root))
import main as CLI
from modules.preprocess import load_image
w=root/'output/phase-pitch-trace-20261006'
original=load_image(str(root/'test_scores/verovio/beethoven_op18no1_bravura_p1.png'))
modified=original.copy(); modified[251:300,392:425]=(255,255,255)
records=[]
for name,dx in [('without-p',0),('without-p-x0.5',.5)]:
    image=modified if dx==0 else cv2.warpAffine(modified,np.float32([[1,0,dx],[0,1,0]]),(modified.shape[1],modified.shape[0]),flags=cv2.INTER_LINEAR,borderValue=(255,255,255))
    path=w/(name+'.png');cv2.imencode('.png',image)[1].tofile(str(path))
    out=w/name;out.mkdir(exist_ok=True);log=io.StringIO()
    with patch.object(sys,'argv',['main.py',str(path),'--no-debug','--output-dir',str(out)]),contextlib.redirect_stdout(log): CLI.run_page(CLI.parse_args(),str(path),0,str(out))
    (out/'source.log').write_text(log.getvalue(),encoding='utf-8')
    doc=json.loads(next(out.glob('*_라벨.json')).read_text(encoding='utf-8'))
    targets=[l for l in doc['labels'] if l['staff'] in (0,1) and 400<=l['x']<=415]
    records.append(dict(case=name,dx=dx,cleared_rect=[392,251,425,300],music=doc['music'],targets=targets))
    print(name,json.dumps(targets,ensure_ascii=False),flush=True)
(w/'counterfactual.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for case in ('original','x0.5'):
    before=root/'output/beta-recheck-20261006/source'/('beethoven_op18no1_bravura_p1' if case=='original' else 'phase-0.5-0')
    after=w/case
    assert json.loads(next(before.glob('*_라벨.json')).read_text(encoding='utf-8'))==json.loads(next(after.glob('*_라벨.json')).read_text(encoding='utf-8'))
    assert next(before.glob('*_계이름.png')).read_bytes()==next(after.glob('*_계이름.png')).read_bytes()
print('읽기 추적 전후 원본/이동본 전체JSON·PNG바이트 일치')
