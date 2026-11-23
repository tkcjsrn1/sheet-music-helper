"""공통 중심 추정 변경의 합성 사진 12입력 회귀를 실제 CLI로 확인한다."""
import contextlib,hashlib,io,json,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));import main as CLI
work=ROOT/'output/dynamic-join-fix-20261006';rows=[]
for case in sorted((ROOT/'output/header-symbols/photo-matrix-final/after').iterdir()):
 if not case.is_dir():continue
 path=ROOT/'output/header-symbols/photo_inputs'/f'{case.name}.png'
 old=json.loads((case/'labels.json').read_text(encoding='utf-8'))
 assert old['source']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
 out=work/'photo'/case.name;out.mkdir(parents=True,exist_ok=True);log=io.StringIO()
 argv=['main.py',str(path),'--photo','--no-debug','--output-dir',str(out)]
 with patch.object(sys,'argv',argv),contextlib.redirect_stdout(log):CLI.run_page(CLI.parse_args(),str(path),0,str(out))
 (out/'source.log').write_text(log.getvalue(),encoding='utf-8')
 new=json.loads(next(out.glob('*_라벨.json')).read_text(encoding='utf-8'))
 png=next(out.glob('*_계이름.png'));old_png=next(case.glob('*_계이름.png'))
 row=dict(case=case.name,json_equal=old==new,png_equal=png.read_bytes()==old_png.read_bytes(),old_count=len(old['labels']),new_count=len(new['labels']))
 rows.append(row);(work/'photo-report.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(row,flush=True)
 assert row['json_equal'] and row['png_equal'],('사진 결과 변화: 원본 개별 대조 필요',case.name)
assert len(rows)==12,len(rows)
