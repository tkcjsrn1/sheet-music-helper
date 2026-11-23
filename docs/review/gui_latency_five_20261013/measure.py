"""기존 GUI 계측기를 PDF17의 5쪽에 적용한다. 제품 코드는 변경하지 않는다."""
import hashlib,json,sys
from pathlib import Path
import fitz,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import inspect
import tools.measure_gui_page_latency as meter
code=inspect.getsource(meter.measure)
old='app=gui.SheetHelperApp();app.withdraw();app.output_dir=str(folder)'
assert code.count(old)==1
code=code.replace(old,"""app=gui.SheetHelperApp();app.geometry('1280x700+20+20')
  ready=time.monotonic()+1.3
  while time.monotonic()<ready:
   app.update();time.sleep(.02)
  assert min(app.preview_canvas.winfo_width(),app.preview_canvas.winfo_height())>1, '측정 창 배치 미완료'
  app.withdraw();app.output_dir=str(folder)""")
old='ok=app._select_result_page(index);app.update_idletasks()'
assert code.count(old)==1
code=code.replace(old,'ok=app._select_result_page(index);app.update()')
old="summary['page_count']=len(app._page_sessions)"
assert code.count(old)==1
code=code.replace(old,old+";summary['viewport']=[app.preview_canvas.winfo_width(),app.preview_canvas.winfo_height()];assert min(summary['viewport'])>1, summary")
code=code.replace('assert not errors,errors','assert not errors,dict(errors=errors,summary=summary)')
exec(compile(code,str(meter.__file__),'exec'),vars(meter))
measure=meter.measure

from modules.preprocess import load_image
root=Path(__file__).resolve().parents[3]
folder=Path(sys.argv[1]).resolve()
assert not folder.exists(),'기존 계측을 덮어쓰지 않습니다.'
folder.mkdir();sources=[];inputs=[]
for name,pdf,page in [('db1','chopin_nocturne_Db_6-8.pdf',0),('db6','chopin_nocturne_Db_6-8.pdf',5),('bbm4','chopin_nocturne_Bbm.pdf',3),('em1','chopin_nocturne_Em.pdf',0),('bach1','bach_minuet_Am.pdf',0)]:
    source=root/'test_scores'/pdf
    assert source.is_file(),source
    target=folder/f'{name}.pdf'
    with fitz.open(source) as doc,fitz.open() as one:
        one.insert_pdf(doc,from_page=page,to_page=page);one.save(target)
    a=load_image(str(source),pdf_page=page);b=load_image(str(target))
    assert np.array_equal(a,b),(name,'원본 PDF 페이지 픽셀 불일치')
    sources.append(dict(case=name,source=pdf,page=page+1,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),input_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),pixels_identical=True))
    inputs.append(target)
result={'sources':sources}
for phase,instrument in [('timed',True),('control',False)]:
    result[phase]=measure(inputs,folder/phase,instrument)
    if instrument:
        assert sum(e['stage']=='ui_fit' for e in result[phase]['events'])>=4, '쪽 전환의 예약 갱신 누락'
    (folder/'timings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(phase,result[phase]['summary'],flush=True)
identical=[]
for path in (folder/'timed').iterdir():
    if path.suffix not in ('.png','.json') or path.name=='settings.json':continue
    other=folder/'control'/path.name
    assert path.read_bytes()==other.read_bytes(),path.name
    identical.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert len(identical)==10
result['default_bytes_equal']=identical
(folder/'timings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('5쪽 PNG/JSON 10파일 바이트 동일',flush=True)
