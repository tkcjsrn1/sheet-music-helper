"""동일 입력의 소스/exe/JSON 재렌더링 결과를 릴리스 기록으로 남긴다."""
import collections, hashlib, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path
import numpy as np
from PIL import Image

root = Path.cwd()
info310=json.loads((root/'output/beta352-build-selection.json').read_text(encoding='utf-8'))
sys.path.insert(0,str(root))
build_dir = root/('dist/'+info310['tag'])
package = root/('dist/악보헬퍼-'+info310['tag']+'.zip')
work = root/('output/release-'+info310['short'])
with zipfile.ZipFile(package) as archive:
    assert set(archive.namelist()) == {'악보헬퍼.exe','build-info.json','먼저 읽어주세요.txt','LICENSE','THIRD_PARTY_NOTICES.txt'}
    clean = work/'새 폴더 첫 실행'
    clean.mkdir(parents=True,exist_ok=True)
    archive.extractall(clean)
exe = clean/'악보헬퍼.exe'
assert json.loads((build_dir/'build-info.json').read_text(encoding='utf-8'))['commit']==info310['commit']
assert __import__('subprocess').check_output(['git','rev-parse','HEAD']).decode().strip()==info310['commit']
assert not (clean/'settings.json').exists() and not (clean/'output').exists()
env = dict(os.environ, PYTHONIOENCODING='utf-8')
exe_env = dict(env, PATH=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot'])
assert shutil.which('python',path=exe_env['PATH']) is None

def run(args, log, executable=False):
    result = subprocess.run(args,cwd=root,env=exe_env if executable else env,
                            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    log.write_bytes(result.stdout)
    assert result.returncode == 0, (args,result.returncode,result.stdout[-1200:])

def pixels(path):
    return np.asarray(Image.open(path).convert('RGB'))

bach=root/'output/night-inputs/bach_p1.png'
if not bach.exists():
    import fitz
    bach.parent.mkdir(parents=True,exist_ok=True)
    with fitz.open(root/'test_scores/bach_minuet_Am.pdf') as pdf:
        pdf[0].get_pixmap(dpi=300,alpha=False).save(bach)

results=[]
cases=[('aoharu_p1',root/'sample_images/KakaoTalk_20260731_162400402.png'),
       ('aoharu_p2',root/'sample_images/KakaoTalk_20260731_162400402_01.png'),
       ('aoharu_p3',root/'sample_images/KakaoTalk_20260731_162400402_02.png'),
       ('chopin_Db_p1',root/'tests/fixtures/selftest/chopin_Db_p1.png'),
       ('bach_p1',root/'output/night-inputs/bach_p1.png'),
       ('clef_change_clara1',root/'test_scores/verovio/clara_polonaise_1_bravura_p1.png'),
       ('alto_beethoven1',root/'test_scores/verovio/beethoven_op18no1_bravura_p1.png'),
       ('schubert_restored',root/'test_scores/verovio/schubert_lindenbaum_piano_leipzig_p1.png')]
for name,input_file in cases:
    source=root/'output/strict-beta-352-354-20261014'/name; frozen=work/(name+'_exe'); relabel=work/(name+'_relabel')
    assert source.is_dir(), ('strict 소스 결과 없음',name)
    strict=json.loads((root/'output/strict-beta-352-354-20261014/result.json').read_text(encoding='utf-8'))
    assert next(r for r in strict if r['case']==name)['allowed']
    run([str(exe),'--selftest',str(input_file),str(frozen)],work/(name+'_exe.log'),True)
    source_png=next(source.glob('*_계이름.png')); exe_png=next(frozen.glob('*_계이름.png'))
    source_json=next(source.glob('*_라벨.json')); exe_json=next(frozen.glob('*_라벨.json'))
    doc=json.loads(exe_json.read_text(encoding='utf-8'))
    assert json.loads(source_json.read_text(encoding='utf-8'))==doc
    if name in ('aoharu_p1','chopin_Db_p1'):
        assert exe_json.read_text(encoding='utf-8').replace('\r\n','\n')==(root/'tests/fixtures/selftest'/f'{name}.json').read_text(encoding='utf-8').replace('\r\n','\n')
    assert source_json.read_text(encoding='utf-8').replace('\r\n','\n')==exe_json.read_text(encoding='utf-8').replace('\r\n','\n')
    assert np.array_equal(pixels(source_png),pixels(exe_png))
    run([str(exe),str(input_file),'--relabel',str(exe_json),'--output-dir',str(relabel),'--no-debug'],work/(name+'_relabel.log'),True)
    assert np.array_equal(pixels(exe_png),pixels(next(relabel.glob('*_계이름.png'))))
    if name == 'clef_change_clara1':
        flagged=[r for r in doc['labels'] if 'clef_changed' in r.get('flags',[])]
        assert flagged and all(r['confidence']=='check' for r in flagged)
        print('음자리표 변경 check',len(flagged),flush=True)
    if name in ('alto_beethoven1','alto_beethoven_leipzig') or name.startswith('header_'):
        assert not [l for l in doc['labels'] if l['staff']<4 and 300<=l['x']<380], '기호 위 라벨 재발'
        for staff in (0,1):
            assert len([l for l in doc['labels'] if l['staff']==staff and 400<=l['x']<=415 and l['pitch']=='F4' and l['text']=='파'])==1, '첫 실제 F4 소실'
        print('actual exe header symbols 0 / real first F4 2/2',name,flush=True)
    if name == 'alto_beethoven1':
        from modules.result_legend import ALTO_WARNING
        flagged=[r for r in doc['labels'] if 'clef_alto' in r.get('flags',[])]
        assert flagged and all(r['confidence']=='check' for r in flagged)
        for suffix in ('_exe.log','_relabel.log'):
            log=(work/(name+suffix)).read_text(encoding='utf-8')
            assert ALTO_WARNING in log and '빈 상단 여백' not in log
        print('알토 check/로그/머리말/재렌더링',len(flagged),flush=True)
    if name == 'schubert_restored':
        restored=[l for l in doc['labels'] if (l['x'],l['y'])==(606,1522)]
        assert len(restored)==1 and restored[0]['pitch']=='E4', restored
        print('#217 실제 exe (606,1522) E4 유지',flush=True)
    if name == 'chopin_Db_p1':
        flagged=[r for r in doc['labels'] if 'grace_size' in r.get('flags',[])]
        assert flagged and all(r['confidence']=='check' for r in flagged)
        print('꾸밈음 grace_size check',len(flagged),flush=True)
    unknown=[r for r in doc['labels'] if 'clef_unknown' in r.get('flags',[])]
    if unknown:
        from modules.result_legend import UNKNOWN_CLEF_WARNING
        assert all(r['confidence']=='check' for r in unknown)
        for suffix in ('_exe.log','_relabel.log'):
            assert UNKNOWN_CLEF_WARNING in (work/(name+suffix)).read_text(encoding='utf-8')
        print('음자리표 미검출 check/로그/재렌더링',name,len(unknown),flush=True)
    centers={'moon1':(1,419,1128,'C2','도#'),'organ2':(5,532,1108,'G3','솔'),
             'alto_beethoven1':(0,406,239,'F4','파'),'alto_beethoven_leipzig':(0,402,239,'F4','파'),
             'clara3_bravura':(4,773,1170,'D6','레'),'clara3_leipzig':(4,760,1177,'D6','레'),
             'clara4_bravura':(0,377,313,'E4','미')}
    if name in centers:
        expected=centers[name]
        hits=[l for l in doc['labels'] if (l['staff'],l['x'],l['y'],l['pitch'],l['text'])==expected]
        assert len(hits)==1,(name,expected,hits)
        print('실제 exe 중심·음고 확인',name,expected,flush=True)
    for flag in ('narrow_hole','beam_gap'):
        flagged=[r for r in doc['labels'] if flag in r.get('flags',[])]
        assert all(r['confidence']=='check' for r in flagged), flag
        if flagged: print('새 표시 실제 exe',name,flag,len(flagged),flush=True)
    counts=dict(collections.Counter(label['confidence'] for label in doc['labels']))
    orange=int(np.count_nonzero(np.all(pixels(exe_png)==[210,120,0],axis=2)))
    caution=int(np.count_nonzero(np.all(pixels(exe_png)==[229,79,79],axis=2)))
    if counts.get('check',0): assert orange>0
    if counts.get('caution',0): assert caution>0
    results.append(dict(case=name,input_sha256=hashlib.sha256(input_file.read_bytes()).hexdigest(),
                        labels=len(doc['labels']),confidence=counts,signals=dict(collections.Counter(f for l in doc['labels'] for f in l.get('flags',[]))),staves=len(doc['staves']),music=doc['music'],
                        source_exe_pixels_equal=True,source_exe_json_equal=True,baseline_json_equal=(True if name in ("aoharu_p1","chopin_Db_p1") else None),
                        exe_relabel_pixels_equal=True,check_orange_pixels=orange,caution_light_pixels=caution,
                        exe_png=str(exe_png.relative_to(root)),exe_json=str(exe_json.relative_to(root))))
    print(name,counts,'소스/exe/재렌더링 픽셀과 JSON 일치',flush=True)
# CLI의 기본 output 경로도 새 폴더의 exe 바로 옆에 만들어지는지 확인한다.
run([str(exe),str(cases[0][1]),'--no-debug'],work/'default_output.log',True)
assert len(list((clean/'output').glob('*_계이름.png')))==1
assert len(list((clean/'output').glob('*_라벨.json')))==1
assert not (clean/'settings.json').exists()
# 다른 원본에 라벨 JSON을 얹으려 하면 실제 exe에서도 중단해야 한다.
wrong_json=next((work/'chopin_Db_p1_exe').glob('*_라벨.json'))
rejected=subprocess.run([str(exe),str(cases[0][1]),'--relabel',str(wrong_json),'--output-dir',str(work/'wrong_input'),'--no-debug'],cwd=root,env=exe_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
(work/'wrong_input.log').write_bytes(rejected.stdout)
assert rejected.returncode==1 and b'Traceback' not in rejected.stdout
assert not list((work/'wrong_input').glob('*_계이름.png'))
result=dict(wrong_input_relabel_rejected=True,build_commit=json.loads((build_dir/'build-info.json').read_text(encoding='utf-8'))['commit'],
            cases=results,python_removed_from_path=True,settings_absent_cli_first_run=True,
            exe_adjacent_default_output=True,zip_files=sorted(zipfile.ZipFile(package).namelist()))
(work/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('새 폴더·settings 없음·Python 없는 PATH·exe 옆 output·ZIP5개 통과',flush=True)

# D-3 수정의 원래 confidence는 보존하면서 실제 exe 그림만 certain과 같아야 한다.
import copy
from modules.label_edits import apply_edits
original=json.loads(next((work/'chopin_Db_p1_exe').glob('*_라벨.json')).read_text(encoding='utf-8'))
target=next(l for l in original['labels'] if l['confidence']=='check')
change=dict(action='set_text',before={k:target[k] for k in ('staff','x','y','pitch','text')},after=dict(text='미' if target['text']!='미' else '레'))
edits=dict(version=1,source=original['source'],changes=[change])
edited=apply_edits(original,edits)
selected=next(l for l in edited['labels'] if l['id']==target['id'])
assert selected['edited'] and selected['confidence']=='check' and selected['pitch']==target['pitch']
corrected=work/'edited_labels.json';corrected.write_text(json.dumps(edited,ensure_ascii=False,indent=2),encoding='utf-8')
input_file=root/'tests/fixtures/selftest/chopin_Db_p1.png'
run([str(exe),str(input_file),'--relabel',str(corrected),'--output-dir',str(work/'d3_edited_exe'),'--no-debug'],work/'d3_edited_exe.log',True)
run([sys.executable,'main.py',str(input_file),'--relabel',str(corrected),'--output-dir',str(work/'d3_edited_source'),'--no-debug'],work/'d3_edited_source.log')
actual=next((work/'d3_edited_exe').glob('*_계이름.png'))
assert np.array_equal(pixels(actual),pixels(next((work/'d3_edited_source').glob('*_계이름.png'))))
expected=copy.deepcopy(edited)
label=next(l for l in expected['labels'] if l['id']==target['id']);label['edited']=False;label['confidence']='certain'
expected_json=work/'expected_certain.json';expected_json.write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8')
run([str(exe),str(input_file),'--relabel',str(expected_json),'--output-dir',str(work/'d3_certain_exe'),'--no-debug'],work/'d3_certain_exe.log',True)
assert np.array_equal(pixels(actual),pixels(next((work/'d3_certain_exe').glob('*_계이름.png'))))
result['d3']=dict(edited_check_draws_as_certain=True,source_exe_edited_pixels_equal=True,original_confidence_preserved=True,target=target)
(work/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('D-3 exe 수정 JSON: 진한 글씨·점선 제거·원래 확신도 보존·소스 픽셀 동일',flush=True)
