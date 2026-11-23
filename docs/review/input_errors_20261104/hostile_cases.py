"""합성 오입력을 실제 소스 GUI 작업자로 처리한다. 원본·판정 변경 없음."""
import sys,time,json,shutil,struct,zlib
from pathlib import Path
from unittest.mock import patch
root=Path('F:/akbo-data/tmp/input-errors-20261104');sys.path.insert(0,str(root));import gui
from PIL import Image
b=Path(__file__).parent;inputs=b/'hostile-inputs';inputs.mkdir(exist_ok=False)
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
# 200MP 단색 PNG를 행 단위로 압축한다. 200MP 배열을 만들거나 크기 한도를 해제하지 않는다.
z=zlib.compressobj();row=b'\0'+b'\xff'*2500;parts=[]
for _ in range(10000):
 part=z.compress(row)
 if part:parts.append(part)
parts.append(z.flush())
huge=inputs/'200MP 흰 악보.png';huge.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',20000,10000,1,0,0,0,0))+chunk(b'IDAT',b''.join(parts))+chunk(b'IEND',b''))
Image.new('RGB',(400,500),'white').save(inputs/'빈 쪽.png');Image.new('RGB',(1,1),'white').save(inputs/'저해상도.png')
sys.path.insert(0,str(root/'tests'));from test_photo_correct import page,rotate
Image.fromarray(rotate(page(),4)).save(inputs/'회전 4도.png')
(inputs/'잘린 PDF.pdf').write_bytes(b'%PDF-1.7\n1 0 obj << /Type /Catalog')
original=Path('F:/akbo-data/tmp/gui-performance-20261104/sample_images/KakaoTalk_20260731_162400402.png');shutil.copy2(original,inputs/'한글 공백 악보.png')
results=[]
for name,ok,want in [('빈 쪽.png',False,'악보 줄'),('회전 4도.png',False,'사진 모드'),('저해상도.png',False,'이미지 크기'),('한글 공백 악보.png',True,''),('잘린 PDF.pdf',False,'PDF'),('200MP 흰 악보.png',False,'크기')]:
 target=b/('hostile-'+name.replace('.','-'));target.mkdir()
 with patch('gui.base_dir',return_value=str(target)),patch.object(sys,'argv',['gui.py']):
  app=gui.SheetHelperApp();app.withdraw();app.output_dir=str(target)
  try:
   began=time.perf_counter();app._set_input(str(inputs/name));deadline=time.monotonic()+90
   def poll():
    if time.monotonic()>deadline:app.quit();return
    if app._converting:app.after(25,poll)
    else:app.quit()
   app.after(0,app.start_convert);app.after(25,poll);app.mainloop()
   assert not app._converting,'작업자 제한시간 초과: '+name
   text=app.log_box.get('1.0','end');success=bool(app.result_path)
   assert success==ok,(name,text)
   if not ok:assert want in text and '해결:'in text and '예상치 못한'not in text,(name,text)
   result=dict(case=name,success=success,seconds=time.perf_counter()-began,log=text,png=app.result_path,json=app.labels_path)
   results.append(result);(b/'hostile-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(name,success,flush=True)
  finally:
   widgets=[app]
   for w in widgets:widgets.extend(w.winfo_children())
   owners={name:w for w in widgets for name in(getattr(w,'_tclCommands',None)or[])}
   for timer in app.tk.splitlist(app.tk.call('after','info')):
    owner=owners.get(str(app.tk.call('after','info',timer)[0]).split()[0]);owner.after_cancel(timer)if owner else app.tk.call('after','cancel',timer)
   app._audio_timer=None;app._close_app()
