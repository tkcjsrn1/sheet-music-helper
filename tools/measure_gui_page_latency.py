"""소스 GUI의 실제 다쪽 작업자를 재서 처리 시간과 쪽 전환 시간을 구분한다."""
import argparse,functools,hashlib,json,sys,threading,time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
import modules.preprocess as pp
import modules.result_legend as legend
import modules.verify as verify
import modules.labels_io as labels_io
import main as cli

def measure(inputs,folder,instrument):
 folder.mkdir(parents=True,exist_ok=False);rows=[];state={'page':0};start=time.perf_counter();errors=[];summary={}
 def emit(stage,elapsed,**extra):
  rows.append(dict(stage=stage,seconds=elapsed,page=state['page'],thread='UI' if threading.current_thread() is threading.main_thread() else 'worker',at=time.perf_counter()-start,**extra))
 def wrap(stage,fn):
  @functools.wraps(fn)
  def timed(*args,**kwargs):
   began=time.perf_counter()
   try:return fn(*args,**kwargs)
   finally:emit(stage,time.perf_counter()-began)
  return timed
 with ExitStack() as stack:
  stack.enter_context(patch('gui.base_dir',return_value=str(folder)))
  stack.enter_context(patch.object(sys,'argv',['gui.py']))
  app=gui.SheetHelperApp();app.withdraw();app.output_dir=str(folder)
  app._set_input(str(inputs[0]));app.input_paths=tuple(map(str,inputs));app.output_dir=str(folder)
  if instrument:
   for module,name,stage in [(pp,'load_image','load'),(gui,'preprocess','preprocess_including_load'),(gui,'analyze_staves','headers'),(gui,'detect_noteheads','detect'),(gui,'calculate_pitches','pitch'),(gui,'annotate_accidentals','accidentals'),(gui,'render_solfege_on_image','render'),(legend,'add_keysig_header','header_render'),(legend,'add_legend','legend_render')]:
    stack.enter_context(patch.object(module,name,wrap(stage,getattr(module,name))))
   for module,names in [(gui,('remove_accidental_ghosts','unstable_accidentals','clef_change_suspects','alto_suspects','unknown_clef_suspects','clef_glyph_suspects','to_solfege_batch')),(verify,('drop_beam_ghosts','drop_offstaff_ghosts','diagnose_labels','sloped_beam_suspects','glyph_shape_suspects','grace_size_suspects','narrow_hole_suspects','beam_gap_suspects')),(cli,('apply_chord_rescue',)),(labels_io,('build_document','save_labels'))]:
    for name in names:stack.enter_context(patch.object(module,name,wrap(name,getattr(module,name))))
   for name,stage in [('_show_result','ui_publish'),('_load_preview_image','ui_image_load'),('_fit_zoom','ui_fit'),('_redraw_preview','ui_draw'),('_select_result_page','page_switch'),('_convert_worker','worker_total')]:
    stack.enter_context(patch.object(app,name,wrap(stage,getattr(app,name))))
   original_page=app._convert_page
   def page(*args,**kwargs):
    state['page']+=1
    return wrap('page_total',original_page)(*args,**kwargs)
   stack.enter_context(patch.object(app,'_convert_page',page))
   original_after=app.after
   def after(ms,fn=None,*args):
    if fn is None:return original_after(ms)
    queued=time.perf_counter();worker=threading.current_thread() is not threading.main_thread()
    def callback():
     if worker:emit('ui_queue_wait',time.perf_counter()-queued,callback=getattr(fn,'__name__','callback'))
     return fn(*args)
    result=original_after(ms,callback)
    if worker:emit('thread_schedule_wait',time.perf_counter()-queued)
    return result
   stack.enter_context(patch.object(app,'after',after))
  deadline=time.monotonic()+600;seen_pending=False
  def finish():
   try:
    summary['page_count']=len(app._page_sessions)
    assert len(app._page_sessions)==len(inputs),'쪽 처리 실패'
    switches=[]
    for index in (1,0,1):
     began=time.perf_counter();ok=app._select_result_page(index);app.update_idletasks()
     switches.append(dict(index=index,accepted=ok,actual_index=app._page_index,seconds=time.perf_counter()-began))
     assert ok and app._page_index==index
    summary.update(switches=switches,pending_disabled_seen=seen_pending,elapsed=time.perf_counter()-start)
   except BaseException as exc:errors.append(str(exc))
   finally:app.quit()
  def poll():
   nonlocal seen_pending
   if app._converting:
    if state['page']==2 or app._conversion_status and app._conversion_status[0]==2:
     assert app.next_page_btn.cget('state')=='disabled'
     seen_pending=True
    if time.monotonic()>deadline:errors.append('처리 600초 초과');app.quit();return
    app.after(50,poll)
   else:app.after(150,finish)
  app.after(0,app.start_convert);app.after(50,poll)
  try:app.mainloop()
  finally:
   # 완료 뒤 위젯 소유자가 등록한 예약만 취소한다.
   widgets=[app]
   for widget in widgets:widgets.extend(widget.winfo_children())
   owners={name:w for w in widgets for name in (getattr(w,'_tclCommands',None) or [])}
   for timer in app.tk.splitlist(app.tk.call('after','info')):
    owner=owners.get(str(app.tk.call('after','info',timer)[0]).split()[0])
    owner.after_cancel(timer) if owner else app.tk.call('after','cancel',timer)
   app.destroy()
 assert not errors,errors
 return dict(summary=summary,events=rows)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',nargs=2,type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
 assert not args.output.exists(),'새 측정 폴더를 지정하세요.'
 inputs=[p.resolve(strict=True) for p in args.input];args.output.mkdir(parents=True)
 result=dict(inputs=[dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs])
 for name,instrument in [('timed',True),('control',False)]:
  result[name]=measure(inputs,args.output/name,instrument)
  (args.output/'timings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(name,result[name]['summary'],flush=True)
 hashes=[]
 for actual in (args.output/'timed').glob('*'):
  if actual.suffix not in ('.png','.json') or actual.name=='settings.json':continue
  control=args.output/'control'/actual.name
  assert actual.read_bytes()==control.read_bytes(),actual.name
  hashes.append(dict(file=actual.name,sha256=hashlib.sha256(actual.read_bytes()).hexdigest()))
 assert len(hashes)==4,hashes
 result['default_bytes_equal']=hashes
 (args.output/'timings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('PNG/JSON 4파일 바이트 무변경',flush=True)
if __name__=='__main__':main()
