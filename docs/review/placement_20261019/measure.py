"""고정 JSON 재렌더의 배치만 비교한다. 새 인식이나 정답 판정은 하지 않는다."""
import argparse,copy,hashlib,json,subprocess,sys,types
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'main.py').exists():ROOT=Path.cwd()
sys.path.insert(0,str(ROOT))
import main
from modules import renderer
from modules.labels_io import document_notes,document_staves
from modules.verify import barline_positions


def load_renderer(path):
    module=types.ModuleType('modules._placement_measure');module.__package__='modules'
    code=Path(path).read_text(encoding='utf-8-sig')
    exec(compile(code,str(path),'exec'),module.__dict__)
    return module.render_solfege_on_image


def overlap(a,b):
    return not (a[2]<b[0] or a[0]>b[2] or a[3]<b[1] or a[1]>b[3])


def geometry(doc,placed,bgr):
    sp={s['id']:s['spacing'] for s in doc['staves']}
    dark=(cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)<128).astype(np.uint8)
    bars={s.index:[int(b) for b in barline_positions(dark,s,[r['x'] for r in doc['labels'] if r['staff']==s.index])] for s in document_staves(doc)}
    for s in doc['staves']:
        for y in s['line_ys']:dark[max(0,round(y)-1):round(y)+2,:]=0
    heads=[(r['x']-.62*sp[r['staff']],r['y']-.48*sp[r['staff']],r['x']+.62*sp[r['staff']],r['y']+.48*sp[r['staff']]) for r in doc['labels']]
    boxes=[];head_hits=[];cross=[];edge=[]
    for p in placed:
        i=p['index'];r=doc['labels'][i];scale=sp[r['staff']]
        font_px=max(16,round(scale*1.1));m=max(2,round(font_px*.11))+2+(renderer.CHECK_BOX_PAD if p['render_confidence']=='check' else 0)
        box=(p['x']-m,p['y']-m,p['x']+p['w']+m,p['y']+p['h']+m);boxes.append(box)
        head_hits.extend((i,j) for j,h in enumerate(heads) if overlap(box,h))
        cx=p['x']+p['w']/2
        cross.extend((i,b) for b in bars.get(r['staff'],[]) if min(cx,r['x'])<b<max(cx,r['x']))
        edge.extend((i,b) for b in bars.get(r['staff'],[]) if box[0]<b<box[2])
        x0,y0,x1,y1=map(round,(p['x'],p['y'],p['x']+p['w'],p['y']+p['h']))
        p.update(dx_sp=(cx-r['x'])/scale,gap_sp=p['gap']/scale,
                 ink_pixels=int(dark[max(0,y0):max(0,y1),max(0,x0):max(0,x1)].sum()))
    box_hits=[(placed[i]['index'],placed[j]['index']) for i in range(len(boxes)) for j in range(i+1,len(boxes)) if overlap(boxes[i],boxes[j])]
    # 독립 지표: 정확히 같은 x의 여러 머리 열만 센다. 음악적 동시음의 정답이 아니다.
    columns={}
    for p in placed:
        r=doc['labels'][p['index']];columns.setdefault((r['staff'],r['x']),[]).append(p)
    spreads=[];inversions=[]
    for (staff,x),ps in columns.items():
        ps=sorted(ps,key=lambda p:doc['labels'][p['index']]['y'])
        if len({doc['labels'][p['index']]['y'] for p in ps})<2:continue
        centers=[p['x']+p['w']/2 for p in ps]
        spreads.append((max(centers)-min(centers))/sp[staff])
        for a,b in zip(ps,ps[1:]):
            if doc['labels'][a['index']]['y']<doc['labels'][b['index']]['y'] and a['y']+a['h']/2>b['y']+b['h']/2:inversions.append((a['index'],b['index']))
    def stats(values):return dict(median=float(np.median(values)),p95=float(np.percentile(values,95)),maximum=float(max(values))) if values else dict(median=0,p95=0,maximum=0)
    return dict(labels=len(placed),dx=stats([abs(p['dx_sp']) for p in placed]),gap=stats([p['gap_sp'] for p in placed]),
        centered=sum(abs(p['dx_sp']*sp[doc['labels'][p['index']]['staff']])<=.5 for p in placed),
        wrong_direction=sum(p['side']!=p['want'] for p in placed),far=sum(p['gap_sp']>3 for p in placed),
        exact_x_columns=len(spreads),column_spread=stats(spreads),order_inversions=inversions,
        head_hits=head_hits,box_hits=box_hits,bar_crossings=cross,bar_edge_projections=edge)


def measure(args):
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    fn=load_renderer(args.code)
    strict=json.loads((ROOT/'output/strict-double-connection/result.json').read_text(encoding='utf-8'))
    proof=json.loads((ROOT/'output/release-e141908/verification.json').read_text(encoding='utf-8'))
    paths={r['case']:r for r in proof['cases']};results=[]
    for row in strict:
        name=row['case'];entry=paths[name];jsonpath=ROOT/entry['exe_json'];raw=jsonpath.read_bytes();doc=json.loads(raw);snapshot=copy.deepcopy(doc)
        image_path=Path(row['input']);source_hash=hashlib.sha256(image_path.read_bytes()).hexdigest();assert source_hash==doc['source']['sha256']
        capture={};case_out=out/name;case_out.mkdir(exist_ok=True)
        def traced(image,named,path,**kwargs):
            original=image.copy();old_notes=copy.deepcopy([vars(n) for n,_ in named]);original_pairs=list(named);old_options=copy.deepcopy(kwargs)
            placed=fn(image,named,path,**kwargs)
            assert np.array_equal(image,original) and [vars(n) for n,_ in named]==old_notes and named==original_pairs
            assert kwargs==old_options
            by_id={id(n):i for i,(n,_t) in enumerate(named)}
            assert len(placed)==len(named) and sorted(by_id[id(p['note'])] for p in placed)==list(range(len(named)))
            capture['placed']=[dict(index=by_id[id(p['note'])],text=p['text'],x=p['x'],y=p['y'],w=p['w'],h=p['h'],gap=p['gap'],side=p['side'],want=p['want'],render_confidence=kwargs['confidences'][by_id[id(p['note'])]]) for p in placed]
            capture['metrics']=geometry(doc,capture['placed'],image)
            return placed
        previous=main.render_solfege_on_image
        try:
            main.render_solfege_on_image=traced
            options=types.SimpleNamespace(relabel=str(jsonpath),font_size=18,color='#dc1414',key='')
            main.relabel(options,str(image_path),str(case_out))
        finally:main.render_solfege_on_image=previous
        assert doc==snapshot and jsonpath.read_bytes()==raw and hashlib.sha256(image_path.read_bytes()).hexdigest()==source_hash
        png=next(case_out.glob('*.png'))
        if args.baseline:
            expected=cv2.imdecode(np.fromfile(ROOT/entry['exe_png'],np.uint8),cv2.IMREAD_COLOR);got=cv2.imdecode(np.fromfile(png,np.uint8),cv2.IMREAD_COLOR)
            assert np.array_equal(got,expected),(name,'기존 exe PNG 재현 실패')
        capture.update(case=name,input_sha256=source_hash,json_sha256=hashlib.sha256(raw).hexdigest(),input_json_bytes_unchanged=True,input_objects_unchanged=True,png=str(png.relative_to(ROOT)),spacing=[s['spacing'] for s in doc['staves']],labels=doc['labels'])
        (case_out/'placements.json').write_text(json.dumps(capture,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');results.append(capture)
        (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(name,'labels',len(capture['placed']),'centered',capture['metrics']['centered'],'head_hits',len(capture['metrics']['head_hits']),'box_hits',len(capture['metrics']['box_hits']),flush=True)
    assert len(results)==12


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--code',required=True);p.add_argument('--output',required=True);p.add_argument('--baseline',action='store_true');measure(p.parse_args())
