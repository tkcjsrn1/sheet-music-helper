"""1cbc0d8 대비 사용자 허용된 꾸밈음 신뢰도만 통과시킨다. 깨끗한 8입력은 조표 변화도 거부한다."""
import gzip,json,os,subprocess,sys
from pathlib import Path
root=Path.cwd();work=Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=False)
baseline={r['case']:r['actual'] for r in json.loads(gzip.decompress((root/'docs/releases/1cbc0d8/approved-strict.json.gz').read_bytes()))}
cases=[('aoharu_p1','sample_images/KakaoTalk_20260731_162400402.png'),('aoharu_p2','sample_images/KakaoTalk_20260731_162400402_01.png'),('aoharu_p3','sample_images/KakaoTalk_20260731_162400402_02.png'),('chopin_Db_p1','tests/fixtures/selftest/chopin_Db_p1.png'),('bach_p1','output/night-inputs/bach_p1.png'),('clef_change_clara1','test_scores/verovio/clara_polonaise_1_bravura_p1.png'),('alto_beethoven1','test_scores/verovio/beethoven_op18no1_bravura_p1.png'),('schubert_restored','test_scores/verovio/schubert_lindenbaum_piano_leipzig_p1.png')]
def allowed(a,b):
    if a==b:return True
    if {k:v for k,v in a.items() if k not in ('confidence','flags')}!={k:v for k,v in b.items() if k not in ('confidence','flags')}:return False
    old=set(a.get('flags',[]));new=set(b.get('flags',[]))
    return b['confidence']=='check' and a['confidence'] in ('certain','caution','check') and old<=new and new-old=={'grace_size'}
probe=dict(x=1,y=2,text='도',confidence='certain',flags=[])
assert allowed(probe,dict(probe,confidence='check',flags=['grace_size']))
assert not allowed(probe,dict(probe,x=2,confidence='check',flags=['grace_size']))
assert not allowed(probe,dict(probe,confidence='check',flags=['other']))
rows=[]
for name,path in cases:
    target=work/name
    p=subprocess.run([sys.executable,'main.py',str(root/path),'--output-dir',str(target),'--no-debug'],capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8'),creationflags=subprocess.CREATE_NO_WINDOW)
    (work/(name+'.log')).write_bytes(p.stdout+p.stderr);assert p.returncode==0,(name,p.returncode)
    new=json.loads(next(target.glob('*_라벨.json')).read_text(encoding='utf-8'));old=baseline[name]
    row=dict(case=name,before=old,after=new,allowed=False);rows.append(row)
    (work/'result.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    assert {k:v for k,v in old.items() if k!='labels'}=={k:v for k,v in new.items() if k!='labels'},(name,'깨끗한 입력 문맥/조표 변화')
    assert len(old['labels'])==len(new['labels']),(name,'라벨 생김/사라짐')
    row['changed']=[dict(before=a,after=b) for a,b in zip(old['labels'],new['labels']) if a!=b]
    assert all(allowed(a,b) for a,b in zip(old['labels'],new['labels'])),(name,'허용 밖 라벨 변화',row['changed'])
    row['allowed']=True
    (work/'result.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(name,'라벨',len(new['labels']),'허용 꾸밈음 변경',len(row['changed']),flush=True)
assert len(rows)==8 and all(r['allowed'] for r in rows)
print('STRICT8_PASS',flush=True)