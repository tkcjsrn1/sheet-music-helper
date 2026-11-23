"""#312 전체 행을 보존하고 #310/#329 승인된 추가만 단계별로 확인한다."""
import collections,gzip,json,os,subprocess,sys
from pathlib import Path
root=Path.cwd();work=Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=False)
baselines={r['case']:r['before'] for r in json.loads(gzip.decompress(Path(__file__).with_name('strict-result.json.gz').read_bytes()))}
cases=[('aoharu_p1','sample_images/KakaoTalk_20260731_162400402.png'),('aoharu_p2','sample_images/KakaoTalk_20260731_162400402_01.png'),('aoharu_p3','sample_images/KakaoTalk_20260731_162400402_02.png'),('chopin_Db_p1','tests/fixtures/selftest/chopin_Db_p1.png'),('bach_p1','output/night-inputs/bach_p1.png'),('clef_change_clara1','test_scores/verovio/clara_polonaise_1_bravura_p1.png'),('alto_beethoven1','test_scores/verovio/beethoven_op18no1_bravura_p1.png'),('schubert_restored','test_scores/verovio/schubert_lindenbaum_piano_leipzig_p1.png')]
control=work/'disable_second_pair.py'
control.write_text('''import runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import modules.notehead_detect as detect
original=detect._detect_noteheads_in_band
def without_second_pair(*args,**kwargs):
    kwargs['second_pair_split']=False
    return original(*args,**kwargs)
detect._detect_noteheads_in_band=without_second_pair
sys.argv=['main.py']+sys.argv[1:]
runpy.run_path('main.py',run_name='__main__')
''',encoding='utf-8')
def compare(old,new,case,phase):
    assert {k:v for k,v in old.items() if k!='labels'}=={k:v for k,v in new.items() if k!='labels'},(case,phase,'문맥 변화')
    key=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True)
    remaining=collections.Counter(map(key,old['labels']));kept=[];added=[]
    for label in new['labels']:
        encoded=key(label)
        if remaining[encoded]:remaining[encoded]-=1;kept.append(label)
        else:added.append(label)
    assert kept==old['labels'],(case,phase,'기존 행 변경/삭제/순서 변경')
    return added
rows=[]
for name,relative in cases:
    row=dict(case=name,allowed=False);rows.append(row)
    old=baselines[name];row['before']=old
    for phase,script in [('second_disabled',control),('actual',root/'main.py')]:
        target=work/(name+'_'+phase)
        p=subprocess.run([sys.executable,str(script),str(root/relative),'--output-dir',str(target),'--no-debug'],capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8'),creationflags=subprocess.CREATE_NO_WINDOW)
        (work/(name+'_'+phase+'.log')).write_bytes(p.stdout+p.stderr);assert p.returncode==0,(name,phase,p.returncode)
        row[phase]=json.loads(next(target.glob('*_라벨.json')).read_text(encoding='utf-8'))
        (work/'result.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    row['middle_added']=compare(old,row['second_disabled'],name,'#310')
    assert all(l['confidence']=='caution' and 'chord_middle_added' in l['flags'] for l in row['middle_added']),(name,'#310 허용 밖 추가')
    row['second_pair_added']=compare(row['second_disabled'],row['actual'],name,'#329')
    row['total_added']=compare(old,row['actual'],name,'#312 전체 비교')
    row['allowed']=True
    (work/'result.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(name,'기존 행/문맥 무변경, 가운데 추가',len(row['middle_added']),'2도 분할 추가',len(row['second_pair_added']),flush=True)
assert len(rows)==8 and all(row['allowed'] for row in rows)
