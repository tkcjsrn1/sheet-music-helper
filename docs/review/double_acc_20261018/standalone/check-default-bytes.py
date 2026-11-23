"""기본 3입력 PNG/JSON 전후 바이트 대조. 전체 검사 종료 뒤 순차 실행한다."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
R=Path.cwd();O=R/'output/double-acc-standalone-20261018';W=O/'default-bytes';W.mkdir(exist_ok=True)
# 두 소비 모듈 이외 제품은 origin/main과 같아야 기준 함수 치환이 유효하다.
base_info=json.loads((O/'baseline-main.json').read_text(encoding='utf-8'))
product_paths=['main.py','gui.py','modules']
diff=subprocess.check_output(['git','diff',base_info['commit'],'--name-only','--',*product_paths],text=True).splitlines()
assert set(diff)=={'modules/note_namer.py','modules/label_audio.py'},diff
cases=[('aoharu_p1','sample_images/KakaoTalk_20260731_162400402.png'),
       ('chopin_Db_p1','tests/fixtures/selftest/chopin_Db_p1.png'),
       ('bach_p1','output/night-inputs/bach_p1.png')]
rows=[]
for case,source in cases:
    assert (R/source).is_file(),source
    for version in ('baseline','consumer'):
        target=W/case/version;target.mkdir(parents=True,exist_ok=True)
        assert not list(target.glob('*.json')) and not list(target.glob('*.png')),'기존 결과 재사용 금지'
        script=str(O/'run-baseline-main.py') if version=='baseline' else str(R/'main.py')
        with (W/(case+'-'+version+'.log')).open('wb') as stream:
            p=subprocess.run([sys.executable,script,str(R/source),'--output-dir',str(target),'--no-debug'],
                             cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8'),stdout=stream,stderr=subprocess.STDOUT,timeout=300)
        assert p.returncode==0,(case,version,p.returncode)
    for suffix in ('_계이름.png','_라벨.json'):
        a=next((W/case/'baseline').glob('*'+suffix));b=next((W/case/'consumer').glob('*'+suffix))
        assert a.read_bytes()==b.read_bytes(),(case,suffix,'바이트 불일치')
        rows.append(dict(case=case,input=source,input_sha256=hashlib.sha256((R/source).read_bytes()).hexdigest(),
                         kind=suffix,equal=True,sha256=hashlib.sha256(b.read_bytes()).hexdigest()))
    print(case,'PNG/JSON 바이트0',flush=True)
proof=dict(baseline=json.loads((O/'baseline-main.json').read_text(encoding='utf-8')),
           method='제품 변경은 두 소비 모듈뿐임을 먼저 확인. 별도 프로세스에서 기준 git blob 모듈을 읽고 같은 main으로 대조. 인식 파일 수정0.',
           rows=rows,all_equal=True,typed_detection_connected=False)
(W/'result.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
