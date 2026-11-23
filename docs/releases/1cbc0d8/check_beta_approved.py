"""#312 전체 행과 문맥을 대조하고 10-13 21시 승인된 한 이동만 따로 확인한다."""
import collections,gzip,json,os,subprocess,sys
from pathlib import Path
root=Path.cwd();work=Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=False)
baselines={r['case']:r['before'] for r in json.loads(gzip.decompress(Path('docs/releases/pending-329-333/strict-result.json.gz').read_bytes()))}
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
def approved_move(before,after,case,phase,spacing):
    # CLI 독립 확인·사용자 승인된 정확한 한 쌍만 예외다. 새 이동은 자동 승인하지 않는다.
    if case!='schubert_restored' or phase=='#310':return False
    if (before['staff'],before['x'],before['y'],after['x'],after['y'])!=(2,1983,716,2010,717):return False
    changed={'id','x','y','nx','flags'}
    assert {k:v for k,v in before.items() if k not in changed}=={k:v for k,v in after.items() if k not in changed}
    assert (before['pitch'],before['text'],before['confidence'])==('E4','미#','check')
    # CLAUDE_CHECK의 27px/18sp = 가로 1.5sp. 세로 1px도 정확한 승인 좌표로 제한한다.
    assert spacing==18 and abs(after['x']-before['x'])/spacing<=1.5
    assert after['nx']-before['nx']==1.5
    return True

probe=dict(staff=2,x=1983,y=716,nx=110.167,id='old',pitch='E4',text='미#',confidence='check',flags=['glyph_shape'])
shifted=dict(probe,x=2010,y=717,nx=111.667,id='new',flags=['weak_side_ink'])
assert approved_move(probe,shifted,'schubert_restored','#329',18)
assert not approved_move(probe,dict(shifted,x=2011),'schubert_restored','#329',18)
try:approved_move(probe,dict(shifted,pitch='F4'),'schubert_restored','#329',18)
except AssertionError:pass
else:raise AssertionError('음고 변화가 허용됨')

def compare(old,new,case,phase):
    assert {k:v for k,v in old.items() if k!='labels'}=={k:v for k,v in new.items() if k!='labels'},(case,phase,'문맥 변화')
    key=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True)
    remaining=collections.Counter(map(key,old['labels']));kept=[];added=[];moved=[]
    for label in new['labels']:
        encoded=key(label)
        if remaining[encoded]:remaining[encoded]-=1;kept.append(label)
        else:
            prior=next((l for l in old['labels'] if remaining[key(l)] and approved_move(l,label,case,phase,old['staves'][l['staff']]['spacing'])),None)
            if prior is None:added.append(label)
            else:
                remaining[key(prior)]-=1;moved.append(dict(before=prior,after=label))
    assert not any(remaining.values()) and kept==[l for l in old['labels'] if l not in [m['before'] for m in moved]],(case,phase,'기존 행 변경/삭제/순서 변경')
    return added,moved
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
    row['middle_added'],row['middle_moved']=compare(old,row['second_disabled'],name,'#310')
    assert all(l['confidence']=='caution' and 'chord_middle_added' in l['flags'] for l in row['middle_added']),(name,'#310 허용 밖 추가')
    row['second_pair_added'],row['second_pair_moved']=compare(row['second_disabled'],row['actual'],name,'#329')
    row['total_added'],row['total_moved']=compare(old,row['actual'],name,'#312 전체 비교')
    row['allowed']=True
    (work/'result.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(name,'기존 행/문맥 무변경, 가운데 추가',len(row['middle_added']),'2도 분할 추가',len(row['second_pair_added']),'승인 이동',len(row['second_pair_moved']),flush=True)
assert len(rows)==8 and all(row['allowed'] for row in rows)


