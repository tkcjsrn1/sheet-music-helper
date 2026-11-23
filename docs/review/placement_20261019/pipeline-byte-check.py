import os,json,subprocess,hashlib
from pathlib import Path
root=Path.cwd();out=root/'output/placement-20261019/pipeline';out.mkdir(exist_ok=True)
rows=json.loads((root/'output/strict-double-connection/result.json').read_text(encoding='utf-8'));proof=json.loads((root/'output/release-e141908/verification.json').read_text(encoding='utf-8'))
refs={r['case']:r for r in proof['cases']};results=[]
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',TEMP=str(root/'output/tmp'),TMP=str(root/'output/tmp'))
for row in rows:
 name=row['case']
 if name not in ('aoharu_p1','chopin_Db_p1','bach_p1'):continue
 target=out/name
 with (out/(name+'.log')).open('w',encoding='utf-8') as log:
  run=subprocess.run(['C:/Users/user/Desktop/악보헬퍼/venv/Scripts/python.exe','-B','gui.py','--selftest',row['input'],str(target)],stdout=log,stderr=subprocess.STDOUT,env=env)
 assert run.returncode==0,(name,run.returncode)
 actual=next(target.glob('*.json')).read_bytes();before=(root/refs[name]['exe_json']).read_bytes()
 item=dict(case=name,labels=len(json.loads(actual)['labels']),equal=actual==before,before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(actual).hexdigest())
 results.append(item);print(item,flush=True)
 assert actual==before,(name,'JSON 원시바이트 차이')
(out/'proof.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
