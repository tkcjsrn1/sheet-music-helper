"""실제 CLI 전체 경로에 검출 사본만 연결하여 기존 49쪽 기준과 대조한다."""
import collections,contextlib,importlib.util,io,json,sys,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
import modules
work=ROOT/'output/dynamic-join-fix-20261006'
spec=importlib.util.spec_from_file_location('modules.notehead_detect',work/'candidate_notehead_detect.py')
nd=importlib.util.module_from_spec(spec);sys.modules[spec.name]=nd;modules.notehead_detect=nd;spec.loader.exec_module(nd)
import main as CLI
from tools.replay_report import compare_documents
jobs=json.loads((ROOT/'output/beta-recheck-20261006/inputs.json').read_text(encoding='utf-8'));rows=[]
for job in jobs:
 path=Path(job['path']);out=work/'matrix'/job['name'];out.mkdir(parents=True,exist_ok=True)
 old=json.loads(Path(job['baseline']).read_text(encoding='utf-8'))
 assert old['source']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest() and old['source']['page']==job['page']
 argv=['main.py',str(path),'--no-debug','--output-dir',str(out)];log=io.StringIO()
 with patch.object(sys,'argv',argv),contextlib.redirect_stdout(log):CLI.run_page(CLI.parse_args(),str(path),job['page'],str(out))
 (out/'source.log').write_text(log.getvalue(),encoding='utf-8')
 new=json.loads(next(out.glob('*_라벨*.json')).read_text(encoding='utf-8'))
 row=dict(case=job['name'],kind=job['kind'],old_count=len(old['labels']),new_count=len(new['labels']),differences=compare_documents(old,new))
 row['context_equal']=all(old.get(k)==new.get(k) for k in ('music','staves'))
 before=collections.defaultdict(list);after=collections.defaultdict(list)
 for r in old['labels']:before[(r['staff'],r['x'])].append(r)
 for r in new['labels']:after[(r['staff'],r['x'])].append(r)
 changes=[];missing=[];added=[]
 for key in before.keys()|after.keys():
  a=sorted(before[key],key=lambda r:r['y']);b=sorted(after[key],key=lambda r:r['y'])
  if len(a)!=len(b):missing.extend(a);added.extend(b);continue
  for aa,bb in zip(a,b):
   if aa!=bb:changes.append(dict(before=aa,after=bb))
 row.update(changes=changes,unpaired_before=missing,unpaired_after=added)
 png=next(out.glob('*_계이름*.png'));baseline=next(Path(job['baseline']).parent.glob('*_계이름*.png'))
 row['png_bytes_equal']=png.read_bytes()==baseline.read_bytes()
 rows.append(row);(work/'matrix-report.json').write_text(json.dumps(dict(candidate_sha256=hashlib.sha256((work/'candidate_notehead_detect.py').read_bytes()).hexdigest(),cases=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(job['name'],'labels',row['old_count'],row['new_count'],'changed',len(changes),'unpaired',len(missing),len(added),'context',row['context_equal'],flush=True)
 if missing or not row['context_equal']:raise AssertionError(('개별 확인 필요',job['name'],missing,row['context_equal']))
print('49쪽 사본 대조 완료',flush=True)
