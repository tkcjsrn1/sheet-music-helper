"""고정된 실제exe JSON만 재사용한다. 새 인식/기준 갱신 없이 세 배치를 비교한다."""
import copy
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path.cwd()
ARCHIVE = Path('F:/sheet-music-helper-beta-13d73f6-record-20261018')
BETA = Path('F:/sheet-music-helper-progress-test-20261020')
sys.path.insert(0, str(ROOT))
import main
from modules import renderer

OUT = ROOT/'docs/review/label_lanes_20261019'
LOCAL = ROOT/'output/label-lanes-current-20261020'
OUT.mkdir(parents=True, exist_ok=True)
LOCAL.mkdir(parents=True, exist_ok=True)
sha = lambda value: hashlib.sha256(value).hexdigest()


# 같은 인식 자료에서 renderer만 교체한다. 새 인식·기준 갱신은 하지 않는다.
prior = types.ModuleType('modules._before_407');prior.__package__='modules'
prior_code=subprocess.check_output(['git','show','6ecc797^1:modules/renderer.py']).decode('utf-8')
exec(compile(prior_code,'renderer-before-407','exec'),prior.__dict__)


def make_stack_example():
    """같은 실제 두 음 열의 세 배치 비교. 새 인식은 하지 않는다."""
    case='aoharu_p1';box=(350,540,900,704);scale=2
    row=next(r for r in json.loads((LOCAL/'measurements.json').read_text(encoding='utf-8')) if r['case']==case)
    paths=[ROOT/row['before_png'],ROOT/row['default_png'],ROOT/row['png']]
    width,height=(box[2]-box[0])*scale,(box[3]-box[1])*scale
    canvas=Image.new('RGB',(width,3*(height+44)+42),'white');draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',19)
    draw.text((8,7),'추가 대조 / Aoharu 동일 x 두 음 · 높은 음 위',font=font,fill='black')
    for i,(label,path) in enumerate(zip(('전 / 기존 배치','#407 / 원본 기호 보호','계이름 줄 / 자기 x·상하 순서(공간 부족 시 쪽 원복)'),paths)):
        top=42+i*(height+44);draw.text((8,top+7),label,font=font,fill='black')
        canvas.paste(Image.open(path).convert('RGB').crop(box).resize((width,height)),(0,top+44))
    canvas.save(OUT/'05_aoharu_stack.png')
    return dict(file='05_aoharu_stack.png',case=case,crop=list(box),scale=scale)


def main_preview():
    # 015908d 실제exe의 고정 인식JSON과 같은 조건으로 세 배치를 비교한다.
    refs = {r['case']:r for r in json.loads((BETA/'output/release-015908d/verification.json').read_text(encoding='utf-8'))['cases']}
    inputs = {r['case']:r['input'] for r in json.loads((ARCHIVE/'output/strict-double-connection/result.json').read_text(encoding='utf-8'))}
    results = []
    for case in ('chopin_Db_p1','aoharu_p1','bach_p1'):
        path = Path(refs[case]['exe_json'])
        raw = path.read_bytes()
        doc = json.loads(raw)
        source = Path(inputs[case])
        source_bytes = source.read_bytes()
        assert sha(source_bytes) == doc['source']['sha256']
        capture = {}
        for mode in ('before','default','lanes'):
            folder = LOCAL/case/mode
            folder.mkdir(parents=True,exist_ok=True)
            def traced(image,named,target,**opts):
                frozen = copy.deepcopy([vars(n) for n,_ in named]), list(named), image.copy(), copy.deepcopy(opts)
                status={}
                ps = (prior.render_solfege_on_image if mode=='before' else renderer.render_solfege_on_image)(image,named,target,**opts,**(dict(placement_mode='lanes',layout_status=status) if mode=='lanes' else {}))
                if mode=='lanes':capture['lane_status']=status
                assert [vars(n) for n,_ in named] == frozen[0] and named == frozen[1]
                assert np.array_equal(image,frozen[2]) and opts == frozen[3]
                assert len(ps) == len(named)
                assert sorted((id(p['note']),p['text']) for p in ps) == sorted((id(n),t) for n,t in named)
                capture[mode] = [dict(index=i,text=p['text'],staff=p['note'].staff_index,note_x=p['note'].x,note_y=p['note'].y,
                    x=p['x'],y=p['y'],w=p['w'],h=p['h'],lane=p.get('lane',False),gap=p['gap']) for i,p in enumerate(ps)]
                return ps
            previous = main.render_solfege_on_image
            try:
                main.render_solfege_on_image = traced
                main.relabel(SimpleNamespace(relabel=str(path),font_size=18,color='#dc1414',key=''),str(source),str(folder))
            finally:
                main.render_solfege_on_image = previous
            assert path.read_bytes() == raw and source.read_bytes() == source_bytes
            png = next(folder.glob('*.png'))
            capture[mode+'_png'] = str(png.relative_to(ROOT))
        before = Path(refs[case]['exe_png']).read_bytes()
        assert (ROOT/capture['default_png']).read_bytes() == before, (case,'기본PNG바이트차이')
        image = cv2.imdecode(np.frombuffer(source_bytes,np.uint8),cv2.IMREAD_COLOR)
        a = cv2.imdecode(np.frombuffer(before,np.uint8),cv2.IMREAD_COLOR)
        b = cv2.imdecode(np.fromfile(ROOT/capture['lanes_png'],np.uint8),cv2.IMREAD_COLOR)
        protected = np.any(image!=255,axis=2)
        worse = np.any(np.abs(b.astype(np.int16)-image.astype(np.int16)) > np.abs(a.astype(np.int16)-image.astype(np.int16)),axis=2) & protected
        assert not worse.any(),(case,'원본화소악화',int(worse.sum()))
        moved = [p for p in capture['lanes'] if p['lane']]
        for p in moved:
            assert abs(p['x']+p['w']/2-p['note_x']) <= .5
        lane_staffs = sorted({p['staff'] for p in moved})
        counts={s:sum(p['staff']==s for p in capture['lanes']) for s in sorted({p['staff'] for p in capture['lanes']})}
        assert not moved or len(moved)==len(capture['lanes']), '한 페이지 안에서 방식을 섞으면 안 됨'
        for s in lane_staffs: assert sum(p['staff']==s for p in moved) == counts[s]
        result=dict(before_png=capture['before_png'],default_png=capture['default_png'],json_reference='015908d actual exe',before_renderer_commit='6ecc797^1',lane_status=capture['lane_status'],case=case,labels=len(doc['labels']),json_sha256=sha(raw),json_raw_bytes_equal=True,
            source_sha256=sha(source_bytes),source_bytes_equal=True,input_objects_equal=True,default_png_bytes_equal=True,
            lane_labels=len(moved),moved_labels=sum((p['x'],p['y'])!=(q['x'],q['y']) for p,q in zip(capture['lanes'],capture['default'])),lane_staffs=lane_staffs,fallback_staffs=[s for s in counts if s not in lane_staffs],
            staff_label_counts=counts,source_pixels_worsened=int(worse.sum()),png=capture['lanes_png'],
            default=capture['default'],lanes=capture['lanes'])
        results.append(result)
        print(case,'lane_staffs',lane_staffs,'fallback',result['fallback_staffs'],'labels',len(moved),flush=True)
        (LOCAL/'measurements.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    db=next(r for r in results if r['case']=='chopin_Db_p1')
    imgs=[Image.open(ROOT/db['before_png']).convert('RGB'),
          Image.open(ROOT/db['default_png']).convert('RGB'),
          Image.open(ROOT/db['png']).convert('RGB')]
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',19)
    specs=[('01_irregular',(980,1290,1980,1660),'반복 음형 · 들쭉날쭉'),
           ('02_chord',(500,2670,1190,2930),'화음 · 운지·악센트'),
           ('03_dense',(1420,2650,2420,2950),'밀집 구간'),
           ('04_fingering_zoom',(550,2700,1205,2815),'운지·악센트 확대'),
           ('06_chopin_bars10_12',(350,2470,2470,3070),'쇼팽10~12마디 · 글자 겹침 확대')]
    records=[]
    for name,original_box,title in specs:
        x0,y0,x1,y1=original_box
        relevant=[p for p in db['lanes'] if x0<=p['note_x']<=x1 and y0<=p['note_y']<=y1 and p['lane']]
        if relevant:
            y0=max(0,min(y0,min(p['y']-10 for p in relevant)))
            y1=min(imgs[0].height,max(y1,max(p['y']+p['h']+10 for p in relevant)))
        box=x0,y0,x1,y1
        scale=2 if name in ('04_fingering_zoom','06_chopin_bars10_12') else 1
        width=(x1-x0)*scale; height=(y1-y0)*scale
        panel_h=height+44
        canvas=Image.new('RGB',(max(width,700),3*panel_h+42),'white')
        draw=ImageDraw.Draw(canvas)
        draw.text((8,7),title+' / 같은 범위·배율',font=font,fill='black')
        for i,(label,img) in enumerate(zip(('전 / 기존 배치','#407 / 원본 기호 보호','계이름 줄 / 공간 부족이면 쪽 전체 원복'),imgs)):
            top=42+i*panel_h
            draw.text((8,top+7),label,font=font,fill='black')
            canvas.paste(img.crop(box).resize((width,height)),(0,top+44))
        canvas.save(OUT/(name+'.png'))
        records.append(dict(file=name+'.png',original_crop=list(original_box),crop=list(box),scale=scale))
    records.append(make_stack_example())
    (OUT/'crops.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    import gzip
    with gzip.open(OUT/'measurements.json.gz','wt',encoding='utf-8') as stream:json.dump(results,stream,ensure_ascii=False,indent=2)
    print('완료: 고정실악보JSON3쪽·인식재실행0·#407 기본PNG/원본JSON바이트변화0',flush=True)


if __name__ == '__main__': main_preview()