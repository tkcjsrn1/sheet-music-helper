"""현재 main의 바뀐 두 소비 모듈만 기준 커밋 원본으로 읽는 별도 실행 — 제품 파일은 바꾸지 않는다."""
import hashlib,importlib.util,json,runpy,sys
from pathlib import Path
R=Path.cwd();O=R/'output/double-acc-standalone-20261018'
sys.path.insert(0,str(R))
import modules
proof=json.loads((O/'baseline-main.json').read_text(encoding='utf-8'))
for name in ('note_namer','label_audio'):
    path=O/('baseline-'+name+'.py')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==proof['modules'][name+'.py']
    spec=importlib.util.spec_from_file_location('modules.'+name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module);setattr(modules,name,module)
sys.argv=['main.py']+sys.argv[1:]
runpy.run_path(str(R/'main.py'),run_name='__main__')
