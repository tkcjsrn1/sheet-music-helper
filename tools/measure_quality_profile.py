"""정답 기반 입력 변형·처리시간 측정(Windows). 제품과 골든은 변경하지 않는다.

정답 생성 명령·범위·한계는 docs/QUALITY_RECHECK_20261007.md 참조.
--check: 정답 좌표 변환 검사. --benchmark-exe <경로>: 세 입력 소스/exe 대조."""
import argparse, copy, csv, ctypes, hashlib, json, os, subprocess, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
OUT = ROOT/'output/quality-20261007'


def worker(image, folder):
    started = time.perf_counter()
    import main as cli
    imported = time.perf_counter()-started
    import modules.verify as verify
    stages = Counter()
    for name in ('preprocess','analyze_staves','detect_noteheads','drop_beam_ghosts',
                 'drop_offstaff_ghosts','calculate_pitches','annotate_accidentals',
                 'remove_accidental_ghosts','apply_chord_rescue','render_solfege_on_image'):
        target=cli if hasattr(cli,name) else verify
        original = getattr(target,name)
        def timed(*args, _name=name, _fn=original, **kwargs):
            tick=time.perf_counter()
            try:return _fn(*args,**kwargs)
            finally:stages[_name]+=time.perf_counter()-tick
        setattr(target,name,timed)
    sys.argv=['main.py',str(image),'--no-debug','--output-dir',str(folder),'--save-labels',str(folder/'labels.json')]
    tick=time.perf_counter()
    try:cli.run_page(cli.parse_args(),str(image),0,str(folder))
    finally:
        elapsed=time.perf_counter()-tick
        class Memory(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak','working','pp','p','np','n','pf','peakpf')]
        counters=Memory(); counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
        api=ctypes.WinDLL('psapi').GetProcessMemoryInfo
        api.argtypes=[ctypes.c_void_p,ctypes.POINTER(Memory),ctypes.c_ulong]
        if not api(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):raise ctypes.WinError()
        (folder/'timing.json').write_text(json.dumps(dict(import_s=imported,pipeline_s=elapsed,stages_s=stages,peak_working_bytes=counters.peak)),encoding='utf-8')


def transform_truth(t,sx,sy,dx,dy):
    t=copy.deepcopy(t)
    for n in t['notes']:
        n['x']=(n['x']+.5)*sx-.5+dx;n['y']=(n['y']+.5)*sy-.5+dy
    for st in t['staves']:
        st['line_ys']=[(y+.5)*sy-.5+dy for y in st['line_ys']]
        for k in ('x0','x1'):st[k]=(st[k]+.5)*sx-.5+dx
        for k in ('clefs','keysigs'):
            for e in st[k]:e['x']=(e['x']+.5)*sx-.5+dx
    for b in t['boxes']:
        x0,y0,x1,y1=b['box'];b['box']=[(x0+.5)*sx-.5+dx,(y0+.5)*sy-.5+dy,(x1+.5)*sx-.5+dx,(y1+.5)*sy-.5+dy]
    return t


def measure():
    import cv2, numpy as np
    import measure_verovio as V
    from measure_omission_rate import match
    OUT.mkdir(exist_ok=True,parents=True)
    jobs=[]
    for i,path in enumerate(sorted((ROOT/'sample_images').glob('KakaoTalk_20260731_162400402*.png')),1):
        assert i<=3
        jobs.append((f'aoharu_p{i}',path,'aoharu'))
    assert len(jobs)==3
    jobs += [(p.stem,p,'verovio') for p in sorted((ROOT/'test_scores/verovio').glob('*_p1.png'))]
    assert len(jobs)==23
    variants=['base','identity_warp','x025','x05','x075','y05','xy05','resize090','resize110','jpeg70']
    representative=lambda n:n.startswith(('aoharu','beethoven','clara_polonaise_2','schubert'))
    records=[]
    for name,path,kind in jobs:
        image=cv2.imdecode(np.fromfile(path,np.uint8),cv2.IMREAD_COLOR);assert image is not None
        if kind=='verovio':truth=json.loads((OUT/'truth'/f'{name}.json').read_text(encoding='utf-8'))
        else:
            truth=[r.split('\t') for r in (ROOT/'tests/golden'/f'{name}.tsv').read_text(encoding='utf-8').splitlines() if r and not r.startswith('#')]
        for variant in variants if representative(name) else ['base']:
            sx=sy=1.;dx=dy=0.
            if variant.startswith('x0'):dx={'x025':.25,'x05':.5,'x075':.75}[variant]
            if variant=='y05':dy=.5
            if variant=='xy05':dx=dy=.5
            if variant.startswith('resize'):
                f=.9 if variant=='resize090' else 1.1
                changed=cv2.resize(image,None,fx=f,fy=f,interpolation=cv2.INTER_LINEAR)
                sx=changed.shape[1]/image.shape[1];sy=changed.shape[0]/image.shape[0]
            elif variant=='jpeg70':changed=cv2.imdecode(cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,70])[1],cv2.IMREAD_COLOR)
            elif variant=='base':changed=image
            else:
                changed=cv2.warpAffine(image,np.float32([[1,0,dx],[0,1,dy]]),(image.shape[1],image.shape[0]),flags=cv2.INTER_LINEAR,borderValue=(255,255,255))
                if variant=='identity_warp':assert np.array_equal(changed,image)
            folder=OUT/'runs'/name/variant;folder.mkdir(exist_ok=True,parents=True)
            temp=folder/'input.png';temp.write_bytes(cv2.imencode('.png',changed)[1].tobytes())
            tick=time.perf_counter()
            with (folder/'cli.log').open('w',encoding='utf-8') as log:
                proc=subprocess.run([sys.executable,__file__,'--worker',str(temp),str(folder)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
            row=dict(name=name,kind=kind,variant=variant,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),input_sha256=hashlib.sha256(temp.read_bytes()).hexdigest(),sx=sx,sy=sy,dx=dx,dy=dy,status=proc.returncode,wall_s=time.perf_counter()-tick)
            if (folder/'timing.json').exists():row.update(json.loads((folder/'timing.json').read_text()))
            if proc.returncode==0:
                doc=json.loads((folder/'labels.json').read_text(encoding='utf-8'));labels=doc['labels']
                row.update(labels=len(labels),music=doc['music'],staves=len(doc['staves']),confidence=dict(Counter(l['confidence'] for l in labels)))
                if kind=='verovio':e=V.evaluate_page(name,doc,transform_truth(truth,sx,sy,dx,dy))
                else:
                    heads=[dict(cx=(float(r[1])+.5)*sx-.5+dx,cy=(float(r[2])+.5)*sy-.5+dy,pitch=r[3],text=r[5]) for r in truth]
                    sp=float(np.median([s['spacing'] for s in doc['staves']]))
                    pairs,used_h,used_l=match(heads,labels,sp);pairs=dict(pairs);rows=[]
                    for i,h in enumerate(heads):
                        got=labels[pairs[i]] if i in pairs else None
                        status='누락' if got is None else '음고' if h['pitch']!=got['pitch'] else '표기' if h['text']!=got['text'] else '맞음'
                        rows.append(dict(x=h['cx'],y=h['cy'],truth=h['pitch'],text_truth=h['text'],status=status,label=got))
                    e=dict(rows=rows,ghosts=[l for i,l in enumerate(labels) if i not in used_l],header={})
                row.update(truth=len(e['rows']),counts=dict(Counter(r['status'] for r in e['rows'])),ghosts=len(e['ghosts']),header=e['header'])
                (folder/'evaluation.json').write_text(json.dumps(e,ensure_ascii=False),encoding='utf-8')
            temp.unlink()  # 한 번에 한 변형만 둔다. 원본과 결과 JSON은 보존.
            records.append(row)
            (OUT/'report.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            print(name,variant,row['status'],row.get('counts'),round(row['wall_s'],2),flush=True)


def benchmark(exe):
    import cv2,numpy as np
    root=ROOT;exe=exe.resolve();assert exe.is_file();out=root/'output/quality-20261007/performance';out.mkdir(parents=True,exist_ok=True)
    temp=OUT/'tmp';temp.mkdir(parents=True,exist_ok=True);env=dict(os.environ,PYTHONIOENCODING='utf-8',TEMP=str(temp),TMP=str(temp));rows=[]
    cases=[('aoharu_p1',root/'sample_images/KakaoTalk_20260731_162400402.png'),('chopin_Db_p1',root/'tests/fixtures/selftest/chopin_Db_p1.png'),('bach',root/'output/beta-recheck-20261006/raster/bach.png')]
    for name,path in cases:
        assert path.exists(),path
        timings={}
        for mode,cmd in (('source',[sys.executable,str(root/'tools/measure_quality_profile.py'),'--worker',str(path),str(out/name/'source')]),('exe',[str(exe),'--selftest',str(path),str(out/name/'exe')])):
            folder=out/name/mode;folder.mkdir(parents=True,exist_ok=True)
            tick=time.perf_counter()
            with (folder/'cli.log').open('w',encoding='utf-8') as log:r=subprocess.run(cmd,env=env,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            timings[mode]=time.perf_counter()-tick
            assert r.returncode==0,(name,mode,r.returncode)
        source=out/name/'source';frozen=out/name/'exe';a=json.loads((source/'labels.json').read_text(encoding='utf-8'));b=json.loads(next(frozen.glob('*라벨.json')).read_text(encoding='utf-8'))
        assert a==b,(name,'JSON')
        read=lambda p:cv2.imdecode(np.fromfile(p,np.uint8),cv2.IMREAD_COLOR)
        assert np.array_equal(read(next(source.glob('*계이름*.png'))),read(next(frozen.glob('*계이름*.png')))),(name,'PNG')
        row=dict(name=name,wall_s=timings,source_metrics=json.loads((source/'timing.json').read_text()),source_exe_json_png_equal=True)
        rows.append(row);(out/'report.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print(name,timings,flush=True)




def self_check():
    t=dict(notes=[dict(x=10,y=20)],staves=[dict(line_ys=[20,24],x0=2,x1=30,clefs=[dict(x=2)],keysigs=[dict(x=5)])],boxes=[dict(box=[1,2,3,4])])
    original=copy.deepcopy(t)
    assert transform_truth(t,1,1,0,0)==t
    moved=transform_truth(t,1,1,.5,.25)
    assert moved['notes'][0]==dict(x=10.5,y=20.25)
    assert moved['staves'][0]['line_ys']==[20.25,24.25]
    resized=transform_truth(t,2,3,0,0)
    assert resized['notes'][0]==dict(x=20.5,y=61.)
    assert resized['boxes'][0]['box']==[2.5,7.,6.5,13.]
    assert t==original
    print('정답의 좌표·오선·기호 상자 변환과 원본 보존: 통과')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',nargs=2);p.add_argument('--check',action='store_true');p.add_argument('--benchmark-exe',type=Path);args=p.parse_args()
    if args.worker:worker(Path(args.worker[0]),Path(args.worker[1]))
    elif args.check:self_check()
    elif args.benchmark_exe:benchmark(args.benchmark_exe)
    else:measure()
