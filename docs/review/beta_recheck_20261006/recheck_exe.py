"""실제 베타 exe로 49쪽과 부분화소 5입력을 다시 처리한다. 제품/정답 수정 없음."""
import collections, contextlib, copy, hashlib, io, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from PIL import Image

ROOT=Path.cwd(); sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import main as CLI
from modules.preprocess import load_image
from tools.replay_report import compare_documents
WORK=ROOT/'output/beta-recheck-20261006'
RELEASE=json.loads((ROOT/'docs/releases/87de5d5/artifacts.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(RELEASE['exe']['path']).upper()==RELEASE['exe']['sha256']
assert sha(RELEASE['zip']['path']).upper()==RELEASE['zip']['sha256']
clean=WORK/'새 ZIP'; assert not clean.exists(), '재실행은 새 출력 폴더를 사용하세요'
clean.mkdir()
with zipfile.ZipFile(RELEASE['zip']['path']) as archive:
    assert set(archive.namelist())=={'악보헬퍼.exe','build-info.json','먼저 읽어주세요.txt','LICENSE','THIRD_PARTY_NOTICES.txt'}
    archive.extractall(clean)
exe=clean/'악보헬퍼.exe'; assert sha(exe)==sha(RELEASE['exe']['path'])
env=dict(os.environ,PATH=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot'],PYTHONPATH='',PYTHONIOENCODING='utf-8')
assert shutil.which('python',path=env['PATH']) is None and not (clean/'settings.json').exists()
jobs=json.loads((WORK/'inputs.json').read_text(encoding='utf-8'))
assert len(jobs)==49
for phase in ('0.25-0','0.5-0','0.75-0','0-0.5','0.5-0.5'):
    jobs.append(dict(kind='phase',name='phase-'+phase,path=str(ROOT/'output/header-symbols'/f'phase-{phase}.png'),page=0,baseline=None))
rows=[]
for index,job in enumerate(jobs,1):
    path=Path(job['path']); name=job['name']; source_sha=sha(path)
    if path.suffix.lower()=='.pdf':
        inp=WORK/'raster'/f'{name}.png'; inp.parent.mkdir(exist_ok=True)
        original=load_image(str(path),pdf_page=job['page'],pdf_dpi=300)
        cv2.imencode('.png',original)[1].tofile(str(inp))
        assert np.array_equal(original,load_image(str(inp))), 'PDF를 옮기며 화소가 달라졌습니다'
        del original
    else: inp=path
    source=WORK/'source'/name; frozen=WORK/'exe'/name; source.mkdir(parents=True)
    log=io.StringIO()
    argv=['main.py',str(inp),'--output-dir',str(source),'--no-debug']
    with patch.object(sys,'argv',argv),contextlib.redirect_stdout(log):
        CLI.run_page(CLI.parse_args(),str(inp),0,str(source))
    (source/'run.log').write_text(log.getvalue(),encoding='utf-8')
    result=subprocess.run([str(exe),'--selftest',str(inp),str(frozen)],cwd=clean,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    frozen.mkdir(parents=True,exist_ok=True);(frozen/'run.log').write_bytes(result.stdout)
    assert result.returncode==0,(name,result.returncode,result.stdout[-1500:])
    sp=next(source.glob('*_계이름.png'));ep=next(frozen.glob('*_계이름.png'))
    sj=next(source.glob('*_라벨.json'));ej=next(frozen.glob('*_라벨.json'))
    a=json.loads(sj.read_text(encoding='utf-8'));b=json.loads(ej.read_text(encoding='utf-8'))
    row=dict(index=index,kind=job['kind'],case=name,original_file=path.name,page=job['page'],original_sha256=source_sha,raster_sha256=sha(inp),staves=len(b['staves']),labels=len(b['labels']),confidence=dict(collections.Counter(l['confidence'] for l in b['labels'])),music=b['music'],exe_exit=0,source_exe_json_equal=a==b,source_exe_png_bytes_equal=sp.read_bytes()==ep.read_bytes())
    differences=compare_documents(a,b);row['source_exe_differences']=differences
    with Image.open(sp) as sim,Image.open(ep) as eim:
        row['source_exe_pixels_equal']=np.array_equal(np.asarray(sim.convert('RGB')),np.asarray(eim.convert('RGB')))
    if job['baseline']:
        baseline=Path(job['baseline']);old=json.loads(baseline.read_text(encoding='utf-8'))
        assert old['source']['sha256']==source_sha and old['source']['page']==job['page']
        normalized=copy.deepcopy(b)
        # PDF→무손실PNG로 달라지는 원본 식별3항목만 되돌린다. 크기/dpi/라벨은 제외하지 않는다.
        for key in ('file','page','sha256'): normalized['source'][key]=old['source'][key]
        row['baseline_json_equal']=old==normalized
        row['baseline_differences']=compare_documents(old,normalized)
        row['baseline_json_sha256']=sha(baseline)
        bp=next(baseline.parent.glob('*_계이름*.png'))
        row['baseline_png_bytes_equal']=bp.read_bytes()==ep.read_bytes()
    if name.startswith('beethoven_op18no1_') or job['kind']=='phase':
        end=362 if 'leipzig' in name else 365
        symbols=[l for l in b['labels'] if l['staff']<4 and 300<=l['x']<=end]
        first=[len([l for l in b['labels'] if l['staff']==s and 400<=l['x']<=415 and l['pitch']=='F4' and l['text']=='파']) for s in (0,1)]
        row['header_symbol_labels']=symbols; row['first_F4_counts']=first
        assert not symbols and first==[1,1],(name,symbols,first)
        if job['kind']=='phase':
            original_path=ROOT/'test_scores/verovio/beethoven_op18no1_bravura_p1.png'
            assert sha(original_path)!=source_sha,'위상 변환을 건너뛴 대조입니다'
        else:
            with Image.open(ep) as im: im.crop((235,180,455,920)).save(WORK/(name+'_header_detail.png'))
    rows.append(row)
    (WORK/'report.json').write_text(json.dumps(dict(build_commit=RELEASE['build_commit'],exe_sha256=RELEASE['exe']['sha256'],cases=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{index}/{len(jobs)} {name}: 라벨{row['labels']} source/exe={row['source_exe_json_equal']} 기존기준={row.get('baseline_json_equal','해당없음')} PNG={row['source_exe_pixels_equal']}",flush=True)
    assert row['source_exe_json_equal'] and row['source_exe_png_bytes_equal'] and row['source_exe_pixels_equal'],row
    assert row.get('baseline_json_equal',True) and row.get('baseline_png_bytes_equal',True),row
assert len(rows)==54
assert not (clean/'settings.json').exists()
print('완료: 49쪽 + 부분화소5, 소스/exe 및 기존 수정후기준 일치',flush=True)