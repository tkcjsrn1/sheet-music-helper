"""합성 라벨로 수정창 이유 안내의 줄바꿈·버튼 영역을 확인한다. 인식/원본 악보 없음."""
import ctypes,json,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from PIL import ImageGrab
R=Path.cwd();sys.path.insert(0,str(R));ctypes.windll.user32.SetProcessDPIAware()
import gui
W=R/'output/review-reasons-layout-20261016';W.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=W) as tmp,patch.object(gui,'base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
 app=gui.SheetHelperApp();records=[]
 try:
  app.geometry('1280x700+20+20');app._edit_session=dict(doc=dict(labels=[dict(staff=0,x=100,y=100,pitch='D4',text='레',confidence='check',flags=['double_acc','flat_propagated'],edited=False)]),changes=[],placements=[])
  app._open_label_editor();win=app._edit_window;win.geometry('520x520+40+40')
  for name,flags in [('double',['double_acc','flat_propagated']),('beam',['beam_sloped','text_row'])]:
   app._edit_session['doc']['labels'][0]['flags']=flags;app._select_edit_label()
   for _ in range(8):app.update();time.sleep(.03)
   rect=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())
   ImageGrab.grab(bbox=rect).save(W/(name+'.png'))
   row=dict(case=name,text=app._edit_reason.cget('text'),window=list(rect),reason_height=app._edit_reason.winfo_height(),text_required_height=app._edit_reason._label.winfo_reqheight())
   assert row['text_required_height']<=row['reason_height'],row
   for child in win.winfo_children():
    if child.winfo_ismapped():assert child.winfo_y()+child.winfo_height()<=win.winfo_height(),(name,child.winfo_class(),'창 밖 버튼/안내')
   records.append(row)
  (W/'layout.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(records,ensure_ascii=False))
 finally:
  for timer in app.tk.splitlist(app.tk.call('after','info')):app.tk.call('after','cancel',timer)
  app.destroy()