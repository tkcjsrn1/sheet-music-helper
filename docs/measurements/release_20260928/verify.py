import sys,json,subprocess,hashlib,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
root=Path.cwd();sys.path.insert(0,str(root));q=root/'output/release-20260928';exeout=q/'깨끗한 배포/output';report=[]
def same(a,b):
 x=np.asarray(Image.open(a));y=np.asarray(Image.open(b));return x.shape==y.shape and np.array_equal(x,y)
for name in ('aoharu_p1','chopin_Db_p1','bbm2'):
 src=root/'output'/f'{name}_계이름.png';dst=exeout/src.name;j=exeout/f'{name}_라벨.json'
 assert same(src,dst),name
 d=json.loads(j.read_text(encoding='utf-8'));assert d==json.loads((root/'output'/j.name).read_text(encoding='utf-8'))
 keep=q/'source';keep.mkdir(exist_ok=True);shutil.copy2(src,keep/src.name);shutil.copy2(root/'output'/j.name,keep/j.name)
 r=subprocess.run([sys.executable,'main.py',str(q/'inputs'/f'{name}.png'),'--relabel',str(j),'--font-size','18','--output-dir',str(q/'relabel'/name)],capture_output=True,text=True,encoding='utf-8');assert r.returncode==0,r.stdout+r.stderr
 assert same(dst,q/'relabel'/name/dst.name)
 flags=[r for r in d['labels'] if 'accidental_candidate' in r['flags']]
 if name=='bbm2':
  assert {(r['x'],r['y']) for r in flags}=={(1276,312),(1499,2515),(1880,2524),(2202,2515)}
  assert all(r['confidence']=='check' for r in flags)
 report.append(dict(sample=name,labels=len(d['labels']),staves=len(d['staves']),confidence={c:sum(r['confidence']==c for r in d['labels']) for c in ('certain','caution','check')},accidental_checks=len(flags),pixels_equal=True,json_equal=True,relabel_equal=True,input_sha256=hashlib.sha256((q/'inputs'/f'{name}.png').read_bytes()).hexdigest()))
 print(name,'PASS',report[-1],flush=True)
from modules.renderer import LABEL_STYLES
assert LABEL_STYLES['caution']['mix']==0.25
(q/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
im=Image.open(exeout/'bbm2_계이름.png').convert('RGB');sheet=Image.new('RGB',(1200,320),'white');draw=ImageDraw.Draw(sheet)
for i,(x,y) in enumerate([(1276,312),(1499,2515),(1880,2524),(2202,2515)]):
 sheet.paste(im.crop((x-75,y-55,x+75,y+95)).resize((300,300)),(i*300,20));draw.text((i*300,0),str((x,y)),fill='black')
sheet.save(q/'new-checks.jpg',quality=90)
print('ALL_PASS')
