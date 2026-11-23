# 현재 main과 renderer 변경의 실제 JSON 바이트를 순차 대조한다.
import ctypes,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'output/placement-407-merge-20261019'
class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('physical','available','pagefile','available_pagefile','virtual','available_virtual','extended')]
def memory():
    m=Memory();m.length=ctypes.sizeof(m);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));return m.available
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,path):
    assert memory()>=int(2.5*1024**3),'실행 전 메모리 기준 미달'
    with path.open('w',encoding='utf-8') as stream:
        proc=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT)
        while proc.poll() is None:
            if memory()<1024**3:
                subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                raise RuntimeError('메모리 기준 미달: 본인 검사 중단')
            time.sleep(5)
        assert proc.returncode==0,(cmd,proc.returncode)
proof=[]
for case,src in [('chopin_Db_p1','tests/fixtures/selftest/chopin_Db_p1.png'),('aoharu_p1','sample_images/KakaoTalk_20260731_162400402.png')]:
    fixture=ROOT/'tests/fixtures/selftest'/f'{case}.json'; before=fixture.read_bytes()
    old=next((ROOT/'output/selftest-397-20261019'/case).glob('*.json'));oldraw=old.read_bytes()
    target=OUT/case;target.mkdir(exist_ok=True)
    run([sys.executable,'-B','gui.py','--selftest',src,str(target)],OUT/f'{case}.log')
    actual=next(target.glob('*.json'));raw=actual.read_bytes()
    assert raw.replace(b'\r\n',b'\n')==before.replace(b'\r\n',b'\n'),(case,'현재 selftest 기준과 차이')
    assert raw==oldraw,(case,'#414/#407 뒤 JSON 원시바이트 차이')
    assert fixture.read_bytes()==before
    proof.append(dict(case=case,labels=len(json.loads(raw)['labels']),selftest_fixture_lf_equal=True,source_before_after_raw_bytes_equal=True,sha256=sha(actual),fixture_unchanged=True))
    (OUT/'json-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(proof[-1],flush=True)
source=next(r['input'] for r in json.loads((ROOT/'output/strict-double-connection/result.json').read_text(encoding='utf-8')) if r['case']=='bach_p1')
wrapper=OUT/'baseline-bach.py'
wrapper.write_text('''import sys,types,subprocess
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import main
code=subprocess.check_output(['git','show','1d37312:modules/renderer.py']).decode('utf-8')
module=types.ModuleType('modules._comparison');module.__package__='modules'
exec(compile(code,'baseline_renderer.py','exec'),module.__dict__)
main.render_solfege_on_image=module.render_solfege_on_image
sys.argv=['main.py',sys.argv[1],'--output-dir',sys.argv[2],'--no-debug'];sys.stdin=None
main.main()
''',encoding='utf-8')
base=OUT/'bach-baseline';base.mkdir(exist_ok=True);candidate=OUT/'bach-candidate';candidate.mkdir(exist_ok=True)
run([sys.executable,'-B',str(wrapper),source,str(base)],OUT/'bach-baseline.log')
run([sys.executable,'-B','gui.py','--selftest',source,str(candidate)],OUT/'bach-candidate.log')
a=next(base.glob('*.json'));b=next(candidate.glob('*.json'));assert a.read_bytes()==b.read_bytes(),'Bach JSON 바이트 변화'
proof.append(dict(case='bach_p1',labels=len(json.loads(b.read_bytes())['labels']),source_before_after_raw_bytes_equal=True,baseline_renderer_commit='1d37312',before_sha256=sha(a),after_sha256=sha(b)))
(OUT/'json-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(proof[-1],flush=True)
print('selftest2쪽 + 현재 baseline 대조 Bach: 인식 JSON 바이트 변화0')
